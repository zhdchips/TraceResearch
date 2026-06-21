"""Lead Agent Tool Controller — deterministic tool-selection policy (008).

Wraps the LeadAgentRuntime and exposes a tool-based execution loop.
Instead of a fixed pipeline, the controller inspects the current state
and selects the next tool according to a deterministic policy.

The policy is a state machine that mirrors the classic pipeline but
is structured as discrete tool invocations.  This interface is designed
to be replaced with an LLM-based tool selector in a future iteration.

Design constraints (008):
- No real LLM function calling
- No LangGraph
- Classic runtime path preserved
- Tool execution trace events for every call
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from traceresearch.agents.lead_runtime import LeadAgentRuntime, RuntimeState
from traceresearch.agents.runtime_tools import (
    TOOL_REGISTRY,
    ToolCall,
    ToolResult,
    get_tool_by_name,
    is_transition_allowed,
)
from traceresearch.evidence.models import CritiqueDecision, NextPhase
from traceresearch.source_discovery.base import SourceDiscoveryProvider
from traceresearch.trace.models import (
    AgentRole,
    ErrorInfo,
    EventType,
    TraceEvent,
    TraceStatus,
)

logger = logging.getLogger(__name__)


def _read_lead_agent_mode() -> str:
    """Read TRACERESEARCH_LEAD_AGENT_MODE from env, default 'runtime'.

    Valid modes: runtime, tool_controller, langgraph (009).
    """
    value = os.environ.get("TRACERESEARCH_LEAD_AGENT_MODE", "runtime")
    if value not in ("runtime", "tool_controller", "langgraph"):
        logger.warning(
            "TRACERESEARCH_LEAD_AGENT_MODE=%r unknown, falling back to 'runtime'",
            value,
        )
        return "runtime"
    return value


@dataclass
class ToolCallRecord:
    """Immutable record of a tool invocation for trace/debug purposes."""

    tool_name: str
    step_name: str
    status: str
    error: str | None = None
    output_summary: str = ""
    timestamp: str = ""


class LeadAgentToolController:
    """Deterministic tool controller that wraps LeadAgentRuntime.

    Usage::

        state = RuntimeState(run_id=..., run_dir=..., trace_writer=tw)
        runtime = LeadAgentRuntime(state=state, ...)
        controller = LeadAgentToolController(runtime=runtime, state=state)
        state = controller.run_tool_loop(query="...", provider=provider)
    """

    def __init__(
        self,
        runtime: LeadAgentRuntime,
        state: RuntimeState,
        *,
        max_steps: int = 20,
    ) -> None:
        self._runtime = runtime
        self.state = state
        self.max_steps = max_steps
        self._step_count = 0
        self._iteration_count = 0  # critique cycles completed
        self._execution_log: list[ToolCallRecord] = []

    # ------------------------------------------------------------------
    # Tool selection policy
    # ------------------------------------------------------------------

    def select_next_tool(self) -> str | None:
        """Return the next tool name based on current state.

        Deterministic policy:
            initialized → plan_research
            planned → run_research_subagents
            researched → write_report
            drafted → verify_report
            verified → critique_report
            critiqued → check critique decision:
                PASS → finalize_run
                REVISE → route based on next_phase:
                    research → run_research_subagents
                    write → write_report
                    verify → verify_report
                    (unsupported → finalize_run)
                FAIL → finalize_run
            completed / failed → None (stop)
        """
        status = self.state.status

        if status == "initialized":
            return "plan_research"
        if status == "needs_clarification":
            return None  # stop, needs human
        if status == "planned":
            return "run_research_subagents"
        if status == "researched":
            return "write_report"
        if status == "drafted":
            return "verify_report"
        if status == "verified":
            return "critique_report"
        if status == "critiqued":
            critique = self.state.critique_result
            if critique is None:
                return "finalize_run"
            decision = critique.decision
            if decision == CritiqueDecision.PASS:
                return "finalize_run"
            if decision == CritiqueDecision.REVISE:
                # If max_iterations reached, force finalize
                if self._iteration_count >= self.state.max_iterations:
                    logger.info(
                        "max_iterations=%d reached after %d critique cycles, finalizing",
                        self.state.max_iterations, self._iteration_count,
                    )
                    return "finalize_run"
                next_phase = critique.next_phase
                self.state.next_phase = str(next_phase.value) if next_phase else None
                self.state.revision_reason = (
                    "; ".join(critique.missing_perspectives)
                    if critique.missing_perspectives else "revision requested"
                )
                if next_phase == NextPhase.RESEARCH:
                    self.state.status = "planned"  # reset for research re-run
                    return "run_research_subagents"
                elif next_phase == NextPhase.WRITE:
                    self.state.status = "researched"  # reset for write re-run
                    return "write_report"
                elif next_phase == NextPhase.VERIFY:
                    self.state.status = "drafted"  # reset for verify re-run
                    return "verify_report"
                else:
                    logger.warning(
                        "Unsupported next_phase=%s, finalizing",
                        self.state.next_phase,
                    )
                    return "finalize_run"
            if decision == CritiqueDecision.FAIL:
                return "finalize_run"
            return None
        if status == "completed":
            return None
        if status == "failed":
            return None

        logger.warning("Unknown status=%r, stopping", status)
        return None

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def execute_tool(
        self,
        tool_name: str,
        *,
        query: str = "",
        provider: SourceDiscoveryProvider | None = None,
        provider_tool_name: str | None = None,
        eval_case: Any = None,
        writer_mode: str = "deterministic",
        verifier_mode: str = "deterministic",
    ) -> ToolResult:
        """Execute a single tool by delegating to the appropriate runtime step.

        Records LEAD_RUNTIME TOOL_CALL and TOOL_RESULT trace events.
        """
        tool = get_tool_by_name(tool_name)
        if tool is None:
            return ToolResult(
                tool_name=tool_name,
                status="failed",
                error=f"Unknown tool: {tool_name}",
            )

        # Validate transition
        if not is_transition_allowed(self.state.status, tool_name):
            msg = (
                f"Transition not allowed: {self.state.status} → {tool_name}"
            )
            logger.warning(msg)
            self._trace_tool(tool_name, EventType.TOOL_RESULT, msg,
                             status=TraceStatus.FAILED,
                             error=ErrorInfo(type="InvalidTransition", message=msg))
            return ToolResult(
                tool_name=tool_name,
                status="failed",
                error=msg,
            )

        # Trace TOOL_CALL
        self._trace_tool(tool_name, EventType.TOOL_CALL,
                         f"executing {tool_name}")

        # Execute
        try:
            if tool_name == "plan_research":
                self._runtime.plan_research(query, eval_case)
            elif tool_name == "run_research_subagents":
                if provider is None:
                    raise ValueError("provider is required for run_research_subagents")
                self._runtime.run_research_subagents(provider, provider_tool_name)
            elif tool_name == "write_report":
                self._runtime.write_report()
            elif tool_name == "verify_report":
                self._runtime.verify_report(
                    writer_mode=writer_mode, verifier_mode=verifier_mode,
                )
            elif tool_name == "critique_report":
                self._runtime.critique_report()
            elif tool_name == "finalize_run":
                self._runtime.finalize_run(writer_mode=writer_mode)
            else:
                raise ValueError(f"Unhandled tool: {tool_name}")

            self._step_count += 1
            result = ToolResult(
                tool_name=tool_name,
                status="success",
                output_summary=f"{tool_name} completed",
                next_status=self.state.status,
            )

            self._trace_tool(tool_name, EventType.TOOL_RESULT,
                             result.output_summary)

            # Record execution log
            self._execution_log.append(ToolCallRecord(
                tool_name=tool_name,
                step_name=tool_name,
                status="success",
                output_summary=result.output_summary,
                timestamp=datetime.now(timezone.utc).isoformat(),
            ))

            return result

        except Exception as exc:
            self._step_count += 1
            error_msg = str(exc) or type(exc).__name__
            result = ToolResult(
                tool_name=tool_name,
                status="failed",
                error=error_msg,
            )

            self._trace_tool(tool_name, EventType.TOOL_RESULT,
                             error_msg,
                             status=TraceStatus.FAILED,
                             error=ErrorInfo(
                                 type=type(exc).__name__,
                                 message=error_msg,
                             ))

            self._execution_log.append(ToolCallRecord(
                tool_name=tool_name,
                step_name=tool_name,
                status="failed",
                error=error_msg,
                timestamp=datetime.now(timezone.utc).isoformat(),
            ))

            raise

    # ------------------------------------------------------------------
    # Tool loop
    # ------------------------------------------------------------------

    def run_tool_loop(
        self,
        query: str,
        provider: SourceDiscoveryProvider,
        eval_case: Any = None,
        provider_tool_name: str | None = None,
        *,
        writer_mode: str = "deterministic",
        verifier_mode: str = "deterministic",
    ) -> RuntimeState:
        """Run the tool loop until completion or max_steps.

        Equivalent to run_pipeline but uses tool selection at each step.
        Includes early-return handling for needs_clarification and all-failed.

        The tool loop also respects the iteration cap from state.max_iterations:
        the REVISE path counts as a step, and the loop re-enters write/verify/
        critique through normal tool selection.
        """
        self._step_count = 0
        self._iteration_count = 0

        # Step 1: Plan (always first)
        try:
            self.execute_tool("plan_research", query=query, eval_case=eval_case)
        except Exception:
            return self.state

        if self.state.status == "needs_clarification":
            return self.state

        # Step 2: Research (always second)
        try:
            self.execute_tool(
                "run_research_subagents",
                provider=provider,
                provider_tool_name=provider_tool_name,
            )
        except Exception:
            return self.state

        if self.state.status == "failed":
            return self.state

        # Iterative section: write → verify → critique → (loop)
        while self._step_count < self.max_steps:
            # Select and execute next tool
            next_tool = self.select_next_tool()
            if next_tool is None:
                break

            try:
                self.execute_tool(
                    next_tool,
                    query=query,
                    provider=provider,
                    provider_tool_name=provider_tool_name,
                    writer_mode=writer_mode,
                    verifier_mode=verifier_mode,
                )
            except Exception:
                # On tool failure, try to finalize and exit
                logger.exception("Tool %s failed, attempting finalize", next_tool)
                if next_tool != "finalize_run":
                    try:
                        self.state.status = "critiqued"
                        self.execute_tool(
                            "finalize_run",
                            writer_mode=writer_mode,
                        )
                    except Exception:
                        logger.exception("finalize_run also failed")
                break

            # After critique, check iteration cap for REVISE
            if next_tool == "critique_report":
                self._iteration_count += 1
                critique = self.state.critique_result
                if critique and critique.decision == CritiqueDecision.REVISE:
                    if self._iteration_count >= self.state.max_iterations:
                        logger.info(
                            "max_iterations=%d reached after %d cycles, finalizing",
                            self.state.max_iterations, self._iteration_count,
                        )
                        # Force finalize on next iteration
                        self.state.status = "critiqued"
                    # If REVISE with remaining iterations, tool selection
                    # next iteration will route to the right tool
                    continue

            # After finalize, stop
            if next_tool == "finalize_run":
                break

        # If we exited the loop without finalizing, finalize now
        if self.state.status != "completed":
            try:
                # Force status to allow finalize
                if self.state.status not in ("critiqued", "drafted", "verified", "researched"):
                    self.state.status = "critiqued"
                self.execute_tool("finalize_run", writer_mode=writer_mode)
            except Exception:
                logger.exception("finalize_run at loop exit failed")

        return self.state

    # ------------------------------------------------------------------
    # Trace helpers
    # ------------------------------------------------------------------

    def _trace_tool(
        self,
        tool_name: str,
        event_type: EventType,
        output_summary: str,
        *,
        status: TraceStatus = TraceStatus.SUCCESS,
        error: ErrorInfo | None = None,
    ) -> None:
        """Record a LEAD_RUNTIME tool execution trace event."""
        if self.state.trace_writer is None:
            return
        event = TraceEvent(
            trace_id=self.state.trace_writer.next_trace_id(self.state.run_id),
            run_id=self.state.run_id,
            agent_role=AgentRole.LEAD_RUNTIME,
            event_type=event_type,
            tool_name=tool_name,
            input_summary=f"tool={tool_name} step={self._step_count}",
            output_summary=output_summary,
            status=status,
            latency_ms=0,
            error=error,
            created_at=datetime.now(timezone.utc),
        )
        self.state.trace_writer.append(event)

    @property
    def execution_log(self) -> list[ToolCallRecord]:
        return list(self._execution_log)

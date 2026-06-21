"""Serial Agent Harness for TraceResearch MVP runs.

The harness is now a thin wrapper that constructs RuntimeState + LeadAgentRuntime
and delegates pipeline orchestration to the runtime. HARNESS-level trace events,
artifact file writing, and RunResult construction remain here.

006 integration: write→verify→critique are wrapped in an iteration loop
that respects TRACERESEARCH_MAX_RUNTIME_ITERATIONS (default 1).

008 integration: when TRACERESEARCH_LEAD_AGENT_MODE=tool_controller,
the harness delegates to LeadAgentToolController instead of the classic path.

009 integration: when TRACERESEARCH_LEAD_AGENT_MODE=langgraph,
the harness delegates to LeadGraphRuntime (LangGraph StateGraph).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from traceresearch.agents.critic import Critic
from traceresearch.agents.lead_researcher import LeadResearchAgent
from traceresearch.agents.lead_runtime import LeadAgentRuntime, RuntimeState, _read_max_iterations
from traceresearch.agents.lead_tool_controller import LeadAgentToolController, _read_lead_agent_mode
from traceresearch.agents.lead_graph_runtime import LeadGraphRuntime
from traceresearch.agents.llm_verifier import LLMVerifier
from traceresearch.agents.llm_writer import LLMWriter
from traceresearch.agents.planner import Planner
from traceresearch.agents.researcher import Researcher
from traceresearch.agents.verifier_protocol import VerifierProtocol
from traceresearch.agents.writer_protocol import WriterProtocol
from traceresearch.evidence.models import (
    CritiqueDecision,
    EvidenceStatus,
    NextPhase,
    ResearchRun,
    ResearchRunStatus,
)
from traceresearch.evidence.store import EvidenceStore
from traceresearch.harness.artifacts import RunArtifacts
from traceresearch.harness.mode_factory import build_verifier, build_writer
from traceresearch.llm.provider import LLMProvider
from traceresearch.source_discovery.base import SourceDiscoveryError, SourceDiscoveryProvider
from traceresearch.source_discovery.fixture_provider import FixtureSourceProvider
from traceresearch.trace.models import (
    AgentRole,
    ErrorInfo,
    EventType,
    TokenUsage,
    TraceEvent,
    TraceStatus,
)
from traceresearch.trace.writer import TraceWriter


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: ResearchRunStatus
    artifact_dir: Path
    final_report_path: Path | None


class ResearchHarness:
    def __init__(
        self,
        *,
        planner: Planner | None = None,
        researcher: Researcher | None = None,
        lead_researcher: LeadResearchAgent | None = None,
        verifier: VerifierProtocol | None = None,
        critic: Critic | None = None,
        writer: WriterProtocol | None = None,
        writer_mode: str = "deterministic",
        verifier_mode: str = "deterministic",
        llm_provider: LLMProvider | None = None,
        max_concurrent_research_tasks: int | None = None,
    ) -> None:
        self.planner = planner or Planner()
        self.researcher = researcher or Researcher()
        self.lead_researcher = lead_researcher or LeadResearchAgent(
            max_concurrent=max_concurrent_research_tasks,
        )
        self.critic = critic or Critic()

        # Direct injection takes priority over mode-based construction
        if writer is not None:
            self.writer = writer
        else:
            self.writer = build_writer(mode=writer_mode, llm_provider=llm_provider)

        if verifier is not None:
            self.verifier = verifier
        else:
            self.verifier = build_verifier(mode=verifier_mode, llm_provider=llm_provider)

        self.writer_mode = writer_mode
        self.verifier_mode = verifier_mode

    def run(
        self,
        *,
        query: str,
        source_provider: SourceDiscoveryProvider,
        output_dir: str | Path,
    ) -> RunResult:
        return self._run_with_provider(
            query=query,
            provider=source_provider,
            output_dir=output_dir,
            run_id=_new_run_id(None),
            eval_case=None,
            case_id=None,
        )

    def run_fixture(
        self,
        *,
        query: str,
        case_id: str | None,
        output_dir: str | Path,
    ) -> RunResult:
        provider = FixtureSourceProvider(case_id=case_id)
        eval_case = provider.load_eval_case(case_id) if case_id else None
        return self._run_with_provider(
            query=query,
            provider=provider,
            output_dir=output_dir,
            run_id=_new_run_id(case_id),
            eval_case=eval_case,
            case_id=case_id,
        )

    def _run_with_provider(
        self,
        *,
        query: str,
        provider: SourceDiscoveryProvider,
        output_dir: str | Path,
        run_id: str,
        eval_case,
        case_id: str | None,
    ) -> RunResult:
        # --- Setup: artifacts, trace, state, runtime ---
        artifacts = RunArtifacts.create(output_dir, run_id)
        trace = _TraceRecorder(run_id=run_id, writer=TraceWriter(artifacts.trace))
        evidence_store = EvidenceStore(artifacts.evidence)
        provider_tool_name = _provider_tool_name(provider)

        trace.record(
            AgentRole.HARNESS,
            EventType.START,
            "Harness run started",
            f"case_id={case_id or 'none'}; source_provider={provider.provider_name}",
        )

        state = RuntimeState(
            run_id=run_id,
            run_dir=str(artifacts.run_dir),
            trace_writer=trace.writer,
        )

        # Resolve max_iterations from env var (006)
        state.max_iterations = _read_max_iterations()

        runtime = LeadAgentRuntime(
            state=state,
            planner=self.planner,
            lead_researcher=self.lead_researcher,
            writer=self.writer,
            verifier=self.verifier,
            critic=self.critic,
        )

        # --- Choose execution path (008/009) ---
        lead_mode = _read_lead_agent_mode()
        if lead_mode == "tool_controller":
            return self._run_tool_controller_path(
                runtime=runtime,
                state=state,
                query=query,
                provider=provider,
                provider_tool_name=provider_tool_name,
                eval_case=eval_case,
                artifacts=artifacts,
                trace=trace,
                evidence_store=evidence_store,
            )

        if lead_mode == "langgraph":
            return self._run_langgraph_path(
                runtime=runtime,
                state=state,
                query=query,
                provider=provider,
                provider_tool_name=provider_tool_name,
                eval_case=eval_case,
                artifacts=artifacts,
                trace=trace,
            )

        # --- Classic runtime path with iteration (006) ---

        # --- Step 1: Plan ---
        runtime.plan_research(query, eval_case)
        brief = state.research_brief
        _write_json(artifacts.research_brief, brief.model_dump(mode="json"))

        if brief.open_clarifications:
            trace.record(
                AgentRole.HARNESS,
                EventType.FINISH,
                "needs clarification",
                "research stopped before source discovery",
                status=TraceStatus.NEEDS_CLARIFICATION,
            )
            return RunResult(
                run_id=run_id,
                status=ResearchRunStatus.NEEDS_CLARIFICATION,
                artifact_dir=artifacts.run_dir,
                final_report_path=None,
            )

        _write_json(
            artifacts.research_tasks,
            [task.model_dump(mode="json") for task in brief.research_tasks],
        )

        # --- Step 2: Research ---
        runtime.run_research_subagents(provider, provider_tool_name)

        if brief.research_tasks and not state.evidence:
            trace.record(
                AgentRole.HARNESS,
                EventType.FINISH,
                "failed run — no evidence collected",
                "status=failed; all research tasks failed or timed out",
                status=TraceStatus.FAILED,
                error=ErrorInfo(
                    type="AllResearchTasksFailed",
                    message="All research tasks failed or timed out — no evidence collected",
                ),
            )
            return RunResult(
                run_id=run_id,
                status=ResearchRunStatus.FAILED,
                artifact_dir=artifacts.run_dir,
                final_report_path=None,
            )

        trace.record(
            AgentRole.HARNESS,
            EventType.TOOL_RESULT,
            "Evidence Store",
            f"evidence.jsonl contains {len(evidence_store.list_all())} rows",
        )

        # --- Steps 3-5: Iterative write → verify → critique (006) ---
        iteration = 0
        while iteration < state.max_iterations:
            iteration += 1

            # Trace iteration start
            trace.record(
                AgentRole.LEAD_RUNTIME,
                EventType.START,
                f"iter={iteration} next_phase={state.next_phase or 'write'}",
                f"iteration {iteration} starting",
                tool_name="iteration_loop",
            )

            # Write (skip if looping back to verify-only)
            if state.next_phase != "verify":
                runtime.write_report()
                draft = state.draft_report
                artifacts.outline.write_text(draft.outline_markdown, encoding="utf-8")
                artifacts.draft_report.write_text(draft.draft_markdown, encoding="utf-8")

            # Verify
            runtime.verify_report(
                writer_mode=self.writer_mode,
                verifier_mode=self.verifier_mode,
            )
            _write_json(artifacts.verification, state.verification_result.model_dump(mode="json"))

            # Critique
            runtime.critique_report()
            _write_json(artifacts.critique, state.critique_result.model_dump(mode="json"))

            critique = state.critique_result
            decision = critique.decision

            # Record iteration
            state.iteration_index = iteration
            state.iteration_history.append({
                "iteration_index": iteration,
                "decision": decision.value,
                "next_phase": str(critique.next_phase.value) if critique.next_phase else None,
                "revision_reason": (
                    "; ".join(critique.missing_perspectives)
                    if critique.missing_perspectives else None
                ),
            })

            # Trace iteration decision
            trace.record(
                AgentRole.LEAD_RUNTIME,
                EventType.TOOL_RESULT,
                f"iter={iteration} decision={decision.value} next_phase={str(critique.next_phase.value) if critique.next_phase else 'none'}",
                f"critic decision: {decision.value}",
                tool_name="iteration_loop",
            )

            if decision == CritiqueDecision.PASS:
                trace.record(
                    AgentRole.LEAD_RUNTIME,
                    EventType.FINISH,
                    f"iter={iteration} decision=pass",
                    f"iteration {iteration} complete — PASS",
                    tool_name="iteration_loop",
                )
                break
            if decision == CritiqueDecision.FAIL:
                trace.record(
                    AgentRole.LEAD_RUNTIME,
                    EventType.FINISH,
                    f"iter={iteration} decision=fail",
                    f"iteration {iteration} complete — FAIL, finalizing",
                    tool_name="iteration_loop",
                )
                break

            # REVISE — check iteration cap
            if iteration >= state.max_iterations:
                trace.record(
                    AgentRole.LEAD_RUNTIME,
                    EventType.FINISH,
                    f"iter={iteration} decision=revise",
                    f"iteration {iteration} — max_iterations reached, finalizing",
                    tool_name="iteration_loop",
                    status=TraceStatus.SKIPPED,
                )
                break

            # Set up next iteration
            state.revision_reason = (
                "; ".join(critique.missing_perspectives)
                if critique.missing_perspectives else "revision requested"
            )
            next_phase_val = critique.next_phase
            state.next_phase = str(next_phase_val.value) if next_phase_val else None

            # Route based on next_phase
            if next_phase_val == NextPhase.RESEARCH:
                trace.record(
                    AgentRole.LEAD_RUNTIME,
                    EventType.FINISH,
                    f"iter={iteration} decision=revise next_phase=research",
                    f"iteration {iteration} complete — REVISE, looping to research",
                    tool_name="iteration_loop",
                )
                runtime.run_research_subagents(provider, provider_tool_name)
                state.next_phase = "write"
            elif next_phase_val in (NextPhase.WRITE, NextPhase.VERIFY):
                trace.record(
                    AgentRole.LEAD_RUNTIME,
                    EventType.FINISH,
                    f"iter={iteration} decision=revise next_phase={state.next_phase}",
                    f"iteration {iteration} complete — REVISE, looping to {state.next_phase}",
                    tool_name="iteration_loop",
                )
                # will re-enter loop correctly
            else:
                # Unsupported next_phase — break and finalize
                trace.record(
                    AgentRole.LEAD_RUNTIME,
                    EventType.FINISH,
                    f"iter={iteration} decision=revise next_phase={state.next_phase}",
                    f"iteration {iteration} — unsupported next_phase={state.next_phase}, finalizing",
                    tool_name="iteration_loop",
                    status=TraceStatus.SKIPPED,
                )
                break

        # --- Step 6: Finalize ---
        runtime.finalize_run(writer_mode=self.writer_mode)
        final_report = state.final_report
        artifacts.final_report.write_text(final_report.markdown, encoding="utf-8")
        _write_json(artifacts.report_json, final_report.report_json)

        # --- Wrap up ---
        return self._wrap_up_run(
            run_id=run_id,
            query=query,
            artifacts=artifacts,
            trace=trace,
            state=state,
        )

    def _run_tool_controller_path(
        self,
        *,
        runtime: LeadAgentRuntime,
        state: RuntimeState,
        query: str,
        provider: SourceDiscoveryProvider,
        provider_tool_name: str | None,
        eval_case,
        artifacts: RunArtifacts,
        trace: _TraceRecorder,
        evidence_store,
    ) -> RunResult:
        """008: Run pipeline through the deterministic tool controller."""
        trace.record(
            AgentRole.HARNESS,
            EventType.TOOL_CALL,
            "tool_controller path",
            f"lead_agent_mode=tool_controller max_iterations={state.max_iterations}",
        )

        controller = LeadAgentToolController(
            runtime=runtime,
            state=state,
            max_steps=state.max_iterations * 6 + 6,  # generous margin
        )

        # Run the tool loop
        state = controller.run_tool_loop(
            query=query,
            provider=provider,
            eval_case=eval_case,
            provider_tool_name=provider_tool_name,
            writer_mode=self.writer_mode,
            verifier_mode=self.verifier_mode,
        )

        # Write artifacts from state (same contract as classic path)
        if state.research_brief:
            _write_json(artifacts.research_brief, state.research_brief.model_dump(mode="json"))
            _write_json(
                artifacts.research_tasks,
                [task.model_dump(mode="json") for task in state.planned_tasks],
            )

        if state.draft_report:
            artifacts.outline.write_text(
                getattr(state.draft_report, "outline_markdown", ""), encoding="utf-8",
            )
            artifacts.draft_report.write_text(
                getattr(state.draft_report, "draft_markdown", ""), encoding="utf-8",
            )

        if state.verification_result:
            _write_json(artifacts.verification, state.verification_result.model_dump(mode="json"))

        if state.critique_result:
            _write_json(artifacts.critique, state.critique_result.model_dump(mode="json"))

        if state.final_report:
            artifacts.final_report.write_text(state.final_report.markdown, encoding="utf-8")
            _write_json(artifacts.report_json, state.final_report.report_json)

        return self._wrap_up_run(
            run_id=state.run_id,
            query=query,
            artifacts=artifacts,
            trace=trace,
            state=state,
        )

    def _run_langgraph_path(
        self,
        *,
        runtime: LeadAgentRuntime,
        state: RuntimeState,
        query: str,
        provider: SourceDiscoveryProvider,
        provider_tool_name: str | None,
        eval_case,
        artifacts: RunArtifacts,
        trace: _TraceRecorder,
    ) -> RunResult:
        """009: Run pipeline through LangGraph StateGraph."""
        trace.record(
            AgentRole.HARNESS,
            EventType.TOOL_CALL,
            "langgraph path",
            f"lead_agent_mode=langgraph max_iterations={state.max_iterations}",
        )

        graph_runtime = LeadGraphRuntime(runtime=runtime, state=state)

        # Run the graph
        graph_state = graph_runtime.run(
            query=query,
            provider=provider,
            eval_case=eval_case,
            provider_tool_name=provider_tool_name,
            writer_mode=self.writer_mode,
            verifier_mode=self.verifier_mode,
        )

        # After graph execution, RuntimeState has been updated by each node.
        # Write artifacts from state (same contract as classic/tool_controller paths).

        # Plan artifacts
        if state.research_brief:
            _write_json(artifacts.research_brief, state.research_brief.model_dump(mode="json"))
            _write_json(
                artifacts.research_tasks,
                [task.model_dump(mode="json") for task in state.planned_tasks],
            )

        # Only write downstream artifacts if we got past research
        if state.status not in ("needs_clarification", "failed", "initialized", "planned"):

            # Outline & draft
            if state.draft_report:
                artifacts.outline.write_text(
                    getattr(state.draft_report, "outline_markdown", ""),
                    encoding="utf-8",
                )
                artifacts.draft_report.write_text(
                    getattr(state.draft_report, "draft_markdown", ""),
                    encoding="utf-8",
                )

            # Verification
            if state.verification_result:
                _write_json(artifacts.verification, state.verification_result.model_dump(mode="json"))

            # Critique
            if state.critique_result:
                _write_json(artifacts.critique, state.critique_result.model_dump(mode="json"))

        # Final report
        if state.final_report:
            artifacts.final_report.write_text(
                getattr(state.final_report, "markdown", str(state.final_report)),
                encoding="utf-8",
            )
            report_json = getattr(state.final_report, "report_json", None)
            if report_json:
                _write_json(artifacts.report_json, report_json)

        return self._wrap_up_run(
            run_id=state.run_id,
            query=query,
            artifacts=artifacts,
            trace=trace,
            state=state,
        )

    def _wrap_up_run(
        self,
        *,
        run_id: str,
        query: str,
        artifacts: RunArtifacts,
        trace: _TraceRecorder,
        state: RuntimeState,
    ) -> RunResult:
        """Common run finalization: trace + RunResult construction.

        Only validates completed-run trace coverage for COMPLETED runs.
        Early-stop runs (needs_clarification, failed) skip coverage check
        since downstream agents (Writer, Verifier, Critic) never ran.
        """
        # Determine status
        if state.status == "needs_clarification":
            run_status = ResearchRunStatus.NEEDS_CLARIFICATION
        elif state.status == "failed":
            run_status = ResearchRunStatus.FAILED
        else:
            run_status = ResearchRunStatus.COMPLETED

        final_report_path = (
            str(artifacts.final_report)
            if run_status == ResearchRunStatus.COMPLETED and artifacts.final_report.exists()
            else None
        )

        run = ResearchRun(
            run_id=run_id,
            input_query=query,
            status=run_status,
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            artifact_dir=str(artifacts.run_dir),
            final_report_path=final_report_path,
        )
        trace.record(
            AgentRole.HARNESS,
            EventType.FINISH,
            "completed run" if run_status == ResearchRunStatus.COMPLETED else "run finished",
            f"status={run.status.value}",
        )
        if run_status == ResearchRunStatus.COMPLETED:
            trace.writer.validate_completed_run_coverage()
        return RunResult(
            run_id=run.run_id,
            status=run.status,
            artifact_dir=artifacts.run_dir,
            final_report_path=(
                Path(final_report_path) if final_report_path else None
            ),
        )


class _TraceRecorder:
    def __init__(self, *, run_id: str, writer: TraceWriter) -> None:
        self.run_id = run_id
        self.writer = writer
        self.sequence = 1

    def record(
        self,
        agent_role: AgentRole,
        event_type: EventType,
        input_summary: str,
        output_summary: str,
        *,
        task_id: str | None = None,
        tool_name: str | None = None,
        status: TraceStatus = TraceStatus.SUCCESS,
        error: ErrorInfo | None = None,
        latency_ms: int = 0,
        token_usage: TokenUsage | None = None,
        llm_mode: str | None = None,
        llm_model: str | None = None,
        llm_token_usage: TokenUsage | None = None,
        failover_reason: str | None = None,
    ) -> None:
        event = TraceEvent(
            trace_id=f"TR-{self.run_id}-{self.sequence:03d}",
            run_id=self.run_id,
            task_id=task_id,
            agent_role=agent_role,
            event_type=event_type,
            tool_name=tool_name,
            input_summary=input_summary,
            output_summary=output_summary,
            status=status,
            latency_ms=latency_ms,
            token_usage=token_usage,
            error=error,
            llm_mode=llm_mode,
            llm_model=llm_model,
            llm_token_usage=llm_token_usage,
            failover_reason=failover_reason,
            created_at=datetime.now(timezone.utc),
        )
        self.writer.append(event)
        self.sequence += 1


def _new_run_id(case_id: str | None) -> str:
    prefix = case_id or "run"
    return f"{prefix}-{uuid4().hex[:8]}"


def _provider_tool_name(provider: SourceDiscoveryProvider) -> str:
    explicit_tool_name = getattr(provider, "tool_name", None)
    if explicit_tool_name:
        return str(explicit_tool_name)
    if provider.provider_name == "fixture":
        return "fixture.search"
    provider_display_name = getattr(provider, "provider_display_name", None)
    if provider_display_name == "exa":
        return "exa.search"
    if provider.provider_name == "web":
        return "web_search"
    return f"{provider.provider_name}.search"


def _trace_error(error: SourceDiscoveryError) -> ErrorInfo:
    to_trace_error = getattr(error, "to_trace_error", None)
    if callable(to_trace_error):
        return to_trace_error()
    return ErrorInfo(type=error.code, message=str(error))


def _write_json(path: Path, payload: object) -> None:
    """Write *payload* as JSON to *path*.

    If *payload* is a Pydantic model, calls ``model_dump(mode="json")`` first.
    Raises TypeError on non-serializable objects — callers must pass valid data.
    """
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

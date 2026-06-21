"""Lead Graph Runtime — LangGraph adapter for the research pipeline.

Wraps LeadAgentRuntime in a LangGraph StateGraph for declarative,
visualizable orchestration.  Each pipeline stage becomes a graph node;
routing decisions become conditional edges.

Design constraints (009):
- Adapter-first: delegates ALL business logic to LeadAgentRuntime step methods.
- GraphState is routing-only; RuntimeState is execution state.
- Single-writer model: only graph nodes (via runtime) write RuntimeState.
- Deterministic routing (no LLM-driven edge decisions).
- Max iterations enforced structurally at the graph level.

Usage::

    state = RuntimeState(run_id="...", run_dir="...", trace_writer=tw)
    runtime = LeadAgentRuntime(state=state, ...)
    graph_runtime = LeadGraphRuntime(runtime=runtime, state=state)

    final_state = graph_runtime.run(
        query="What is the latest in AI agents?",
        provider=provider,
        writer_mode="deterministic",
        verifier_mode="deterministic",
    )
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from traceresearch.agents.graph_state import (
    GraphState,
    create_initial_graph_state,
    sync_from_runtime_state,
)
from traceresearch.agents.lead_runtime import LeadAgentRuntime, RuntimeState
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

# ---------------------------------------------------------------------------
# Node functions (module-level for LangGraph pickling compatibility)
# ---------------------------------------------------------------------------


def _node_plan_research(state: GraphState) -> GraphState:
    """Graph node: plan research tasks."""
    runtime: LeadAgentRuntime = state["_runtime"]
    rs: RuntimeState = state["_runtime_state"]
    state["current_step"] = "plan_research"

    _trace_node_start(state, "plan_research")

    # collect query from metadata stored in runtime_state
    query = getattr(rs, "_query_cache", "") or ""
    eval_case = getattr(rs, "_eval_case_cache", None)

    try:
        runtime.plan_research(query, eval_case)
    except Exception as exc:
        state["error_message"] = str(exc)
        state["status"] = "failed"
        _trace_node_finish(state, "plan_research", status=TraceStatus.FAILED, error=str(exc))
        return sync_from_runtime_state(state)

    _trace_node_finish(state, "plan_research", output_summary=f"status={rs.status}")
    return sync_from_runtime_state(state)


def _node_run_research_subagents(state: GraphState) -> GraphState:
    """Graph node: execute research subagents."""
    runtime: LeadAgentRuntime = state["_runtime"]
    rs: RuntimeState = state["_runtime_state"]
    state["current_step"] = "run_research_subagents"

    _trace_node_start(state, "run_research_subagents")

    provider: SourceDiscoveryProvider | None = getattr(rs, "_provider_cache", None)
    provider_tool_name: str | None = getattr(rs, "_provider_tool_name_cache", None)

    try:
        runtime.run_research_subagents(provider, provider_tool_name)
    except Exception as exc:
        state["error_message"] = str(exc)
        state["status"] = "failed"
        _trace_node_finish(state, "run_research_subagents", status=TraceStatus.FAILED, error=str(exc))
        return sync_from_runtime_state(state)

    _trace_node_finish(state, "run_research_subagents",
                       output_summary=f"evidence={len(rs.evidence)} failed={len(rs.failed_task_ids)}")
    return sync_from_runtime_state(state)


def _node_write_report(state: GraphState) -> GraphState:
    """Graph node: write draft report."""
    runtime: LeadAgentRuntime = state["_runtime"]
    rs: RuntimeState = state["_runtime_state"]
    state["current_step"] = "write_report"

    _trace_node_start(state, "write_report")

    try:
        runtime.write_report()
    except Exception as exc:
        state["error_message"] = str(exc)
        state["status"] = "failed"
        _trace_node_finish(state, "write_report", status=TraceStatus.FAILED, error=str(exc))
        return sync_from_runtime_state(state)

    _trace_node_finish(state, "write_report",
                       output_summary=f"claims={len(getattr(rs.draft_report, 'claims', []))}")
    return sync_from_runtime_state(state)


def _node_verify_report(state: GraphState) -> GraphState:
    """Graph node: verify claims against evidence."""
    runtime: LeadAgentRuntime = state["_runtime"]
    rs: RuntimeState = state["_runtime_state"]
    state["current_step"] = "verify_report"

    _trace_node_start(state, "verify_report")

    writer_mode: str = getattr(rs, "_writer_mode_cache", "deterministic")
    verifier_mode: str = getattr(rs, "_verifier_mode_cache", "deterministic")

    try:
        runtime.verify_report(writer_mode=writer_mode, verifier_mode=verifier_mode)
    except Exception as exc:
        state["error_message"] = str(exc)
        state["status"] = "failed"
        _trace_node_finish(state, "verify_report", status=TraceStatus.FAILED, error=str(exc))
        return sync_from_runtime_state(state)

    _trace_node_finish(state, "verify_report",
                       output_summary=f"claims_verified={len(getattr(rs.verification_result, 'claim_results', []))}")
    return sync_from_runtime_state(state)


def _node_critique_report(state: GraphState) -> GraphState:
    """Graph node: critique report for missing perspectives."""
    runtime: LeadAgentRuntime = state["_runtime"]
    rs: RuntimeState = state["_runtime_state"]
    state["current_step"] = "critique_report"

    _trace_node_start(state, "critique_report")

    try:
        runtime.critique_report()
    except Exception as exc:
        state["error_message"] = str(exc)
        state["status"] = "failed"
        _trace_node_finish(state, "critique_report", status=TraceStatus.FAILED, error=str(exc))
        return sync_from_runtime_state(state)

    critique = rs.critique_result
    decision_str = str(critique.decision.value) if critique else "unknown"
    _trace_node_finish(state, "critique_report", output_summary=f"decision={decision_str}")

    # Update iteration count (critique completes one iteration cycle)
    rs.iteration_index = rs.iteration_index + 1
    state["iteration_index"] = rs.iteration_index

    # Set revision metadata on RuntimeState for REVISE routing
    if critique and critique.decision == CritiqueDecision.REVISE:
        rs.revision_reason = (
            "; ".join(critique.missing_perspectives)
            if critique.missing_perspectives else "revision requested"
        )
        next_phase_val = critique.next_phase
        rs.next_phase = str(next_phase_val.value) if next_phase_val else None

    # Record iteration history
    if critique:
        rs.iteration_history.append({
            "iteration_index": rs.iteration_index,
            "decision": decision_str,
            "next_phase": str(critique.next_phase.value) if critique.next_phase else None,
            "revision_reason": (
                "; ".join(critique.missing_perspectives)
                if critique.missing_perspectives else None
            ),
        })

    return sync_from_runtime_state(state)


def _node_finalize_run(state: GraphState) -> GraphState:
    """Graph node: produce final report."""
    runtime: LeadAgentRuntime = state["_runtime"]
    rs: RuntimeState = state["_runtime_state"]
    state["current_step"] = "finalize_run"

    _trace_node_start(state, "finalize_run")

    writer_mode: str = getattr(rs, "_writer_mode_cache", "deterministic")

    try:
        runtime.finalize_run(writer_mode=writer_mode)
    except Exception as exc:
        state["error_message"] = str(exc)
        state["status"] = "failed"
        _trace_node_finish(state, "finalize_run", status=TraceStatus.FAILED, error=str(exc))
        return sync_from_runtime_state(state)

    _trace_node_finish(state, "finalize_run", output_summary="final report written")
    return sync_from_runtime_state(state)


# ---------------------------------------------------------------------------
# Conditional routing functions
# ---------------------------------------------------------------------------


def _route_after_plan(state: GraphState) -> Literal["run_research_subagents", "__end__"]:
    """Route from plan_research: continue or early-stop for clarification.

    needs_clarification / failed → END (no Writer.final, no downstream agents).
    """
    status = state.get("status", "")
    if status in ("needs_clarification", "failed"):
        _trace_edge(state, "plan_research", "__end__", "needs_clarification_or_failed")
        return END
    _trace_edge(state, "plan_research", "run_research_subagents", "planned")
    return "run_research_subagents"


def _route_after_research(state: GraphState) -> Literal["write_report", "__end__"]:
    """Route from run_research_subagents: write or early-stop if all failed.

    all-tasks-failed → END (no Writer.final, no downstream agents).
    """
    status = state.get("status", "")
    if status == "failed":
        _trace_edge(state, "run_research_subagents", "__end__", "all_tasks_failed")
        return END
    _trace_edge(state, "run_research_subagents", "write_report", "research_complete")
    return "write_report"


def _route_after_critique(
    state: GraphState,
) -> Literal["finalize_run", "run_research_subagents", "write_report", "verify_report"]:
    """Route from critique_report based on PASS / REVISE / FAIL decision.

    PASS → finalize_run
    REVISE + next_phase → research / write / verify (respecting max_iterations)
    FAIL → finalize_run
    REVISE + max_iterations reached → finalize_run
    """
    decision = state.get("critique_decision", "")
    iteration_index = state.get("iteration_index", 0)
    max_iterations = state.get("max_iterations", 1)

    if decision == "pass":
        _trace_edge(state, "critique_report", "finalize_run", "PASS")
        return "finalize_run"

    if decision == "fail":
        _trace_edge(state, "critique_report", "finalize_run", "FAIL")
        return "finalize_run"

    if decision == "revise":
        # max_iterations check — structural loop prevention
        if iteration_index >= max_iterations:
            _trace_edge(state, "critique_report", "finalize_run",
                        f"REVISE_max_iterations_reached_{iteration_index}>={max_iterations}")
            return "finalize_run"

        next_phase = state.get("next_phase", "write")
        if next_phase == "research":
            _trace_edge(state, "critique_report", "run_research_subagents", "REVISE→research")
            return "run_research_subagents"
        elif next_phase == "verify":
            _trace_edge(state, "critique_report", "verify_report", "REVISE→verify")
            return "verify_report"
        else:
            # Default: REVISE → write
            _trace_edge(state, "critique_report", "write_report", f"REVISE→{next_phase}")
            return "write_report"

    # Unknown decision — default to finalize
    logger.warning("Unknown critique_decision=%r, routing to finalize_run", decision)
    _trace_edge(state, "critique_report", "finalize_run", f"unknown_decision_{decision}")
    return "finalize_run"


# ---------------------------------------------------------------------------
# LeadGraphRuntime
# ---------------------------------------------------------------------------


class LeadGraphRuntime:
    """LangGraph adapter wrapping LeadAgentRuntime.

    Builds a StateGraph from LeadAgentRuntime step methods and runs the
    pipeline through LangGraph's graph execution engine.

    Usage::

        graph_runtime = LeadGraphRuntime(runtime=runtime, state=state)
        final_state = graph_runtime.run(
            query="...",
            provider=provider,
            writer_mode="deterministic",
            verifier_mode="deterministic",
        )
    """

    def __init__(
        self,
        runtime: LeadAgentRuntime,
        state: RuntimeState,
    ) -> None:
        self.runtime = runtime
        self.state = state
        self._graph: StateGraph | None = None
        self._app: Any = None

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def build_graph(self) -> Any:
        """Build the compiled LangGraph StateGraph.

        Returns:
            A compiled LangGraph graph (CompiledStateGraph).
        """
        if self._app is not None:
            return self._app

        graph = StateGraph(GraphState)

        # -- Add nodes --
        graph.add_node("plan_research", _node_plan_research)
        graph.add_node("run_research_subagents", _node_run_research_subagents)
        graph.add_node("write_report", _node_write_report)
        graph.add_node("verify_report", _node_verify_report)
        graph.add_node("critique_report", _node_critique_report)
        graph.add_node("finalize_run", _node_finalize_run)

        # -- Add edges --
        # START → plan
        graph.add_edge(START, "plan_research")

        # plan → research (or END for early-stop)
        graph.add_conditional_edges(
            "plan_research",
            _route_after_plan,
            {
                "run_research_subagents": "run_research_subagents",
                END: END,
            },
        )

        # research → write (or END for early-stop)
        graph.add_conditional_edges(
            "run_research_subagents",
            _route_after_research,
            {
                "write_report": "write_report",
                END: END,
            },
        )

        # write → verify
        graph.add_edge("write_report", "verify_report")

        # verify → critique
        graph.add_edge("verify_report", "critique_report")

        # critique → finalize / research / write / verify (conditional)
        graph.add_conditional_edges(
            "critique_report",
            _route_after_critique,
            {
                "finalize_run": "finalize_run",
                "run_research_subagents": "run_research_subagents",
                "write_report": "write_report",
                "verify_report": "verify_report",
            },
        )

        # finalize → END
        graph.add_edge("finalize_run", END)

        self._graph = graph
        self._app = graph.compile()
        return self._app

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(
        self,
        query: str,
        provider: SourceDiscoveryProvider,
        eval_case: Any = None,
        provider_tool_name: str | None = None,
        *,
        writer_mode: str = "deterministic",
        verifier_mode: str = "deterministic",
    ) -> GraphState:
        """Execute the graph pipeline.

        Caches runtime parameters on RuntimeState for node access,
        builds the initial GraphState, compiles the graph, and invokes it.
        """
        # Cache runtime parameters on RuntimeState for node access
        self.state._query_cache = query
        self.state._eval_case_cache = eval_case
        self.state._provider_cache = provider
        self.state._provider_tool_name_cache = provider_tool_name
        self.state._writer_mode_cache = writer_mode
        self.state._verifier_mode_cache = verifier_mode

        # Resolve max_iterations
        from traceresearch.agents.lead_runtime import _read_max_iterations
        if self.state.max_iterations == 1:
            self.state.max_iterations = _read_max_iterations()

        # Build initial graph state
        initial_state = create_initial_graph_state(
            run_id=self.state.run_id,
            run_dir=self.state.run_dir,
            runtime_state=self.state,
            runtime=self.runtime,
            max_iterations=self.state.max_iterations,
        )

        # Compile and run
        app = self.build_graph()

        # Run the graph
        final_state: GraphState = app.invoke(initial_state)

        return final_state


# ---------------------------------------------------------------------------
# Trace helpers
# ---------------------------------------------------------------------------


def _trace_node_start(state: GraphState, node_name: str) -> None:
    """Record a LANGGRAPH START event for a node."""
    rs = state.get("_runtime_state")
    if rs is None:
        return
    tw = getattr(rs, "trace_writer", None)
    if tw is None:
        return

    event = TraceEvent(
        trace_id=tw.next_trace_id(state["run_id"], prefix="graph"),
        run_id=state["run_id"],
        agent_role=AgentRole.LANGGRAPH,
        event_type=EventType.START,
        tool_name=node_name,
        input_summary=f"graph node starting: {node_name}",
        output_summary=f"status={state.get('status', 'unknown')} iter={state.get('iteration_index', 0)}",
        status=TraceStatus.SUCCESS,
        latency_ms=0,
        created_at=datetime.now(timezone.utc),
    )
    tw.append(event)


def _trace_node_finish(
    state: GraphState,
    node_name: str,
    *,
    output_summary: str = "",
    status: TraceStatus = TraceStatus.SUCCESS,
    error: str | None = None,
) -> None:
    """Record a LANGGRAPH FINISH event for a node."""
    rs = state.get("_runtime_state")
    if rs is None:
        return
    tw = getattr(rs, "trace_writer", None)
    if tw is None:
        return

    error_info: ErrorInfo | None = None
    if error:
        error_info = ErrorInfo(type="NodeExecutionError", message=error)

    event = TraceEvent(
        trace_id=tw.next_trace_id(state["run_id"], prefix="graph"),
        run_id=state["run_id"],
        agent_role=AgentRole.LANGGRAPH,
        event_type=EventType.FINISH,
        tool_name=node_name,
        input_summary=f"graph node finished: {node_name}",
        output_summary=output_summary or f"status={state.get('status', 'unknown')}",
        status=status,
        latency_ms=0,
        error=error_info,
        created_at=datetime.now(timezone.utc),
    )
    tw.append(event)


def _trace_edge(
    state: GraphState,
    from_node: str,
    to_node: str,
    decision: str,
) -> None:
    """Record a LANGGRAPH edge decision trace event."""
    rs = state.get("_runtime_state")
    if rs is None:
        return
    tw = getattr(rs, "trace_writer", None)
    if tw is None:
        return

    iteration_index = state.get("iteration_index", 0)
    next_phase = state.get("next_phase", "")

    detail_parts = [
        f"from={from_node}",
        f"to={to_node}",
        f"decision={decision}",
        f"iter={iteration_index}",
    ]
    if next_phase:
        detail_parts.append(f"next_phase={next_phase}")

    event = TraceEvent(
        trace_id=tw.next_trace_id(state["run_id"], prefix="graph"),
        run_id=state["run_id"],
        agent_role=AgentRole.LANGGRAPH,
        event_type=EventType.TOOL_RESULT,
        tool_name="edge_decision",
        input_summary=", ".join(detail_parts),
        output_summary=f"edge decision: {decision}",
        status=TraceStatus.SUCCESS,
        latency_ms=0,
        created_at=datetime.now(timezone.utc),
    )
    tw.append(event)

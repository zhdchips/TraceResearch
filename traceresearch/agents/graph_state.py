"""LangGraph GraphState — lightweight orchestration state for the StateGraph.

The GraphState is a TypedDict (LangGraph requirement) that carries the
minimum fields needed for graph routing.  The canonical execution state
lives in RuntimeState, which each node reads/writes via _runtime_state.

Design constraints (009):
- GraphState MUST be a TypedDict (LangGraph StateGraph requirement).
- RuntimeState remains the source of truth for execution data.
- GraphState syncs from/to RuntimeState at node boundaries.
- GraphState is fully serializable (no object references).
"""

from __future__ import annotations

from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    """LangGraph orchestrator state.

    This is a lightweight routing state.  The heavy execution state
    (evidence, draft, verification, critique, etc.) lives in RuntimeState.
    Each graph node reads/writes RuntimeState directly and then calls
    _sync_graph_state() to update the visible routing fields.

    Fields marked with ``NotRequired`` are optional and have defaults.
    """

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    run_id: str
    run_dir: str

    # ------------------------------------------------------------------
    # Pipeline status
    # ------------------------------------------------------------------
    status: str  # "initialized" | "planned" | "researched" | "drafted" |
    # "verified" | "critiqued" | "completed" | "failed"

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------
    current_step: str  # name of the node currently executing (e.g. "plan_research")
    next_phase: str  # "research" | "write" | "verify" — for REVISE routing
    iteration_index: int
    max_iterations: int

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------
    critique_decision: str  # "pass" | "revise" | "fail" | ""
    revision_reason: str

    # ------------------------------------------------------------------
    # Error
    # ------------------------------------------------------------------
    error_message: str

    # ------------------------------------------------------------------
    # Artifact paths (relative to run_dir)
    # ------------------------------------------------------------------
    artifact_paths: dict[str, str]

    # ------------------------------------------------------------------
    # Internal (not for serialization, used by LangGraph to carry
    # references between nodes)
    # ------------------------------------------------------------------
    _runtime_state: Any  # RuntimeState instance
    _runtime: Any  # LeadAgentRuntime instance


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_initial_graph_state(
    run_id: str,
    run_dir: str,
    runtime_state: Any,
    runtime: Any,
    *,
    max_iterations: int = 1,
) -> GraphState:
    """Create the initial GraphState before graph execution.

    Args:
        run_id: Unique run identifier.
        run_dir: Output directory for this run.
        runtime_state: RuntimeState instance.
        runtime: LeadAgentRuntime instance.
        max_iterations: Iteration cap (from env or default).

    Returns:
        A GraphState ready for LangGraph invocation.
    """
    return GraphState(
        run_id=run_id,
        run_dir=run_dir,
        status="initialized",
        current_step="",
        next_phase="",
        iteration_index=0,
        max_iterations=max_iterations,
        critique_decision="",
        revision_reason="",
        error_message="",
        artifact_paths={},
        _runtime_state=runtime_state,
        _runtime=runtime,
    )


# ---------------------------------------------------------------------------
# Sync helpers
# ---------------------------------------------------------------------------


def sync_from_runtime_state(state: GraphState) -> GraphState:
    """Pull routing-relevant fields from RuntimeState into GraphState.

    Called after each node so conditional edges see up-to-date data.
    """
    rs = state.get("_runtime_state")
    if rs is None:
        return state

    state["status"] = getattr(rs, "status", state.get("status", "initialized"))
    state["iteration_index"] = getattr(rs, "iteration_index", state.get("iteration_index", 0))
    state["max_iterations"] = getattr(rs, "max_iterations", state.get("max_iterations", 1))
    state["next_phase"] = getattr(rs, "next_phase", state.get("next_phase", "")) or ""

    critique = getattr(rs, "critique_result", None)
    if critique is not None:
        state["critique_decision"] = str(getattr(critique, "decision", ""))
        state["revision_reason"] = getattr(rs, "revision_reason", "") or ""
        if hasattr(critique, "missing_perspectives") and critique.missing_perspectives:
            state["revision_reason"] = "; ".join(critique.missing_perspectives)

    return state

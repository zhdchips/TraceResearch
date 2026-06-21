"""Runtime Tool abstractions for the Tool-Calling Lead Agent (008).

Defines lightweight tool contracts, a registry of the 6 pipeline tools,
and transition validation.  Prepared for future LLM function calling but
currently driven by a deterministic policy.

Design constraints (008):
- No real LLM function calling
- No LangGraph
- No changes to LeadAgentRuntime step methods
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Tool abstractions
# ---------------------------------------------------------------------------


@dataclass
class RuntimeTool:
    """A runtime step exposed as a callable tool.

    Attributes:
        name: Unique short identifier (e.g. "plan_research").
        description: Human-readable purpose statement.
        input_schema: Lightweight contract describing expected params.
        allowed_preconditions: State.status values that allow this tool.
    """

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    allowed_preconditions: list[str] = field(default_factory=list)


@dataclass
class ToolCall:
    """A request to execute a tool."""

    tool_name: str
    step_name: str
    params: dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""


@dataclass
class ToolResult:
    """The outcome of a tool execution."""

    tool_name: str
    status: str  # "success" | "failed" | "skipped"
    output_summary: str = ""
    error: str | None = None
    next_status: str = ""  # state.status after execution


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, RuntimeTool] = {
    "plan_research": RuntimeTool(
        name="plan_research",
        description="Analyze the user query and produce a structured research brief with tasks.",
        input_schema={"query": "str", "eval_case": "Any | None"},
        allowed_preconditions=["initialized", "needs_clarification"],
    ),
    "run_research_subagents": RuntimeTool(
        name="run_research_subagents",
        description="Dispatch research tasks to subagents against a source discovery provider.",
        input_schema={"provider": "SourceDiscoveryProvider", "provider_tool_name": "str | None"},
        allowed_preconditions=["planned"],
    ),
    "write_report": RuntimeTool(
        name="write_report",
        description="Draft a research report from collected evidence.",
        input_schema={},
        allowed_preconditions=["researched", "planned"],  # planned = re-write after REVISE research
    ),
    "verify_report": RuntimeTool(
        name="verify_report",
        description="Verify each claim in the draft against the evidence store.",
        input_schema={"writer_mode": "str", "verifier_mode": "str"},
        allowed_preconditions=["drafted", "researched"],  # researched = verify-only REVISE
    ),
    "critique_report": RuntimeTool(
        name="critique_report",
        description="Critique the draft report for missing perspectives, weak sources, and limitations.",
        input_schema={},
        allowed_preconditions=["verified"],
    ),
    "finalize_run": RuntimeTool(
        name="finalize_run",
        description="Produce the final markdown and JSON report.",
        input_schema={"writer_mode": "str"},
        allowed_preconditions=["critiqued", "drafted", "verified", "researched", "planned"],
    ),
}


# ---------------------------------------------------------------------------
# Transition validation
# ---------------------------------------------------------------------------

# State transition map: current_status → list of allowed tool names
_TRANSITION_MAP: dict[str, list[str]] = {
    "initialized": ["plan_research"],
    "needs_clarification": ["plan_research"],  # re-plan
    "planned": ["run_research_subagents", "finalize_run"],  # finalize on all-failed
    "researched": ["write_report", "verify_report", "finalize_run"],
    "drafted": ["verify_report", "finalize_run"],
    "verified": ["critique_report", "finalize_run"],
    "critiqued": ["finalize_run"],
    "completed": [],
    "failed": ["finalize_run"],
}

# Status after successful tool execution
_NEXT_STATUS_MAP: dict[str, str] = {
    "plan_research": "planned",
    "run_research_subagents": "researched",
    "write_report": "drafted",
    "verify_report": "verified",
    "critique_report": "critiqued",
    "finalize_run": "completed",
}


def is_transition_allowed(current_status: str, tool_name: str) -> bool:
    """Return True if *tool_name* can be executed from *current_status*."""
    allowed = _TRANSITION_MAP.get(current_status, [])
    return tool_name in allowed


def get_next_status(tool_name: str) -> str:
    """Return the expected state.status after executing *tool_name*."""
    return _NEXT_STATUS_MAP.get(tool_name, "completed")


def get_tool_by_name(name: str) -> RuntimeTool | None:
    """Return the RuntimeTool for *name*, or None if not found."""
    return TOOL_REGISTRY.get(name)

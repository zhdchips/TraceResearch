"""Unit tests for runtime tool abstractions (008) —
ToolRegistry, transition validation, tool metadata."""

from __future__ import annotations

import pytest

from traceresearch.agents.runtime_tools import (
    TOOL_REGISTRY,
    RuntimeTool,
    ToolCall,
    ToolResult,
    get_tool_by_name,
    is_transition_allowed,
    get_next_status,
)


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

class TestToolRegistry:
    def test_contains_six_tools(self):
        assert len(TOOL_REGISTRY) == 6

    def test_all_required_tools_present(self):
        expected = {
            "plan_research",
            "run_research_subagents",
            "write_report",
            "verify_report",
            "critique_report",
            "finalize_run",
        }
        assert set(TOOL_REGISTRY.keys()) == expected

    def test_each_tool_has_name_and_description(self):
        for name, tool in TOOL_REGISTRY.items():
            assert tool.name == name
            assert isinstance(tool.description, str)
            assert len(tool.description) > 0

    def test_each_tool_has_allowed_preconditions(self):
        for name, tool in TOOL_REGISTRY.items():
            assert isinstance(tool.allowed_preconditions, list)

    def test_get_tool_by_name(self):
        tool = get_tool_by_name("plan_research")
        assert tool is not None
        assert tool.name == "plan_research"

    def test_get_tool_by_name_missing(self):
        assert get_tool_by_name("nonexistent") is None

    def test_tool_input_schemas(self):
        plan = get_tool_by_name("plan_research")
        assert "query" in plan.input_schema


# ---------------------------------------------------------------------------
# Transition validation
# ---------------------------------------------------------------------------

class TestTransitionValidation:
    def test_initialized_to_plan(self):
        assert is_transition_allowed("initialized", "plan_research") is True

    def test_initialized_to_research_rejected(self):
        assert is_transition_allowed("initialized", "run_research_subagents") is False

    def test_planned_to_research(self):
        assert is_transition_allowed("planned", "run_research_subagents") is True

    def test_researched_to_write(self):
        assert is_transition_allowed("researched", "write_report") is True

    def test_drafted_to_verify(self):
        assert is_transition_allowed("drafted", "verify_report") is True

    def test_verified_to_critique(self):
        assert is_transition_allowed("verified", "critique_report") is True

    def test_critiqued_to_finalize(self):
        assert is_transition_allowed("critiqued", "finalize_run") is True

    def test_critiqued_to_write_rejected(self):
        assert is_transition_allowed("critiqued", "write_report") is False

    def test_completed_allows_nothing(self):
        assert is_transition_allowed("completed", "finalize_run") is False
        assert is_transition_allowed("completed", "plan_research") is False

    def test_unknown_status_rejects_all(self):
        assert is_transition_allowed("unknown_status", "plan_research") is False


# ---------------------------------------------------------------------------
# Next status map
# ---------------------------------------------------------------------------

class TestNextStatus:
    def test_plan_goes_to_planned(self):
        assert get_next_status("plan_research") == "planned"

    def test_research_goes_to_researched(self):
        assert get_next_status("run_research_subagents") == "researched"

    def test_write_goes_to_drafted(self):
        assert get_next_status("write_report") == "drafted"

    def test_verify_goes_to_verified(self):
        assert get_next_status("verify_report") == "verified"

    def test_critique_goes_to_critiqued(self):
        assert get_next_status("critique_report") == "critiqued"

    def test_finalize_goes_to_completed(self):
        assert get_next_status("finalize_run") == "completed"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

class TestToolCall:
    def test_creation(self):
        call = ToolCall(tool_name="plan_research", step_name="plan")
        assert call.tool_name == "plan_research"
        assert call.step_name == "plan"
        assert call.params == {}


class TestToolResult:
    def test_success(self):
        result = ToolResult(
            tool_name="write_report",
            status="success",
            output_summary="done",
            next_status="drafted",
        )
        assert result.status == "success"
        assert result.output_summary == "done"

    def test_failed(self):
        result = ToolResult(
            tool_name="write_report",
            status="failed",
            error="something broke",
        )
        assert result.status == "failed"
        assert result.error == "something broke"

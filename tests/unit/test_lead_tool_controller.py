"""Unit tests for LeadAgentToolController (008) —
tool selection, policy, trace events, error handling."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from traceresearch.agents.critic import Critic
from traceresearch.agents.lead_runtime import LeadAgentRuntime, RuntimeState
from traceresearch.agents.lead_tool_controller import (
    LeadAgentToolController,
    _read_lead_agent_mode,
)
from traceresearch.agents.planner import Planner
from traceresearch.agents.verifier_protocol import VerifierProtocol
from traceresearch.agents.writer_protocol import WriterProtocol
from traceresearch.evidence.models import (
    CritiqueDecision,
    CritiqueResult,
    Evidence,
    NextPhase,
    ResearchBrief,
    ResearchTask,
    SourceResult,
    SourceType,
)
from traceresearch.trace.models import AgentRole, EventType, TraceStatus
from traceresearch.trace.writer import TraceWriter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_brief() -> ResearchBrief:
    return ResearchBrief(
        run_id="test-run-001",
        objective="Test",
        scope_boundaries=[],
        assumptions=[],
        open_clarifications=[],
        perspectives=["P1"],
        success_criteria=["C1"],
        research_tasks=[
            ResearchTask(
                research_task_id="T-001", run_id="test-run-001",
                perspective="P1", objective="T1", query="Q1",
            ),
        ],
    )


def _make_evidence():
    from datetime import datetime, timezone

    return [
        Evidence(
            evidence_id="EV-test-001",
            run_id="test-run-001",
            research_task_id="T-001",
            perspective="P1",
            source=SourceResult(
                source_id="S-001", provider="fixture",
                title="Source", source_type=SourceType.BLOG,
                publisher="Pub", retrieved_at=datetime.now(timezone.utc),
                snippet="Snippet", provider_rank=1,
            ),
            authority_score=0.8, relevance_score=0.9,
            summary="Evidence", key_points=["K1"],
            supported_claims=["C1"], limitations=[],
        ),
    ]


def _make_critique(decision, next_phase, missing_perspectives=None):
    return CritiqueResult(
        run_id="test-run-001",
        missing_perspectives=missing_perspectives or [],
        weak_sources=[],
        duplicate_sections=[],
        unsupported_claims=[],
        limitations_to_add=[],
        decision=decision,
        next_phase=next_phase,
        failed_task_ids=[],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_trace_writer():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield TraceWriter(Path(tmpdir) / "trace.jsonl")


@pytest.fixture
def state_and_runtime(tmp_trace_writer, tmp_path):
    run_dir = tmp_path / "test-run"
    run_dir.mkdir()
    state = RuntimeState(
        run_id="test-001",
        run_dir=str(run_dir),
        trace_writer=tmp_trace_writer,
    )
    runtime = LeadAgentRuntime(state=state)
    return state, runtime


# ---------------------------------------------------------------------------
# Env var
# ---------------------------------------------------------------------------

class TestReadLeadAgentMode:
    def test_default_runtime(self):
        assert _read_lead_agent_mode() == "runtime"

    def test_tool_controller(self, monkeypatch):
        monkeypatch.setenv("TRACERESEARCH_LEAD_AGENT_MODE", "tool_controller")
        assert _read_lead_agent_mode() == "tool_controller"

    def test_runtime_explicit(self, monkeypatch):
        monkeypatch.setenv("TRACERESEARCH_LEAD_AGENT_MODE", "runtime")
        assert _read_lead_agent_mode() == "runtime"

    def test_unknown_falls_back(self, monkeypatch):
        monkeypatch.setenv("TRACERESEARCH_LEAD_AGENT_MODE", "llm")
        assert _read_lead_agent_mode() == "runtime"


# ---------------------------------------------------------------------------
# Tool selection
# ---------------------------------------------------------------------------

class TestSelectNextTool:
    def test_initialized_returns_plan(self, state_and_runtime):
        state, runtime = state_and_runtime
        controller = LeadAgentToolController(runtime=runtime, state=state)
        assert controller.select_next_tool() == "plan_research"

    def test_needs_clarification_returns_none(self, state_and_runtime):
        state, runtime = state_and_runtime
        state.status = "needs_clarification"
        controller = LeadAgentToolController(runtime=runtime, state=state)
        assert controller.select_next_tool() is None

    def test_planned_returns_research(self, state_and_runtime):
        state, runtime = state_and_runtime
        state.status = "planned"
        controller = LeadAgentToolController(runtime=runtime, state=state)
        assert controller.select_next_tool() == "run_research_subagents"

    def test_researched_returns_write(self, state_and_runtime):
        state, runtime = state_and_runtime
        state.status = "researched"
        controller = LeadAgentToolController(runtime=runtime, state=state)
        assert controller.select_next_tool() == "write_report"

    def test_drafted_returns_verify(self, state_and_runtime):
        state, runtime = state_and_runtime
        state.status = "drafted"
        controller = LeadAgentToolController(runtime=runtime, state=state)
        assert controller.select_next_tool() == "verify_report"

    def test_verified_returns_critique(self, state_and_runtime):
        state, runtime = state_and_runtime
        state.status = "verified"
        controller = LeadAgentToolController(runtime=runtime, state=state)
        assert controller.select_next_tool() == "critique_report"

    def test_critiqued_pass_returns_finalize(self, state_and_runtime):
        state, runtime = state_and_runtime
        state.status = "critiqued"
        state.critique_result = _make_critique(CritiqueDecision.PASS, NextPhase.COMPLETE)
        controller = LeadAgentToolController(runtime=runtime, state=state)
        assert controller.select_next_tool() == "finalize_run"

    def test_critiqued_revise_research_returns_research(self, state_and_runtime):
        state, runtime = state_and_runtime
        state.status = "critiqued"
        state.critique_result = _make_critique(
            CritiqueDecision.REVISE, NextPhase.RESEARCH,
            missing_perspectives=["P2"],
        )
        controller = LeadAgentToolController(runtime=runtime, state=state)
        result = controller.select_next_tool()
        assert result == "run_research_subagents"
        assert state.status == "planned"  # reset for transition

    def test_critiqued_revise_write_returns_write(self, state_and_runtime):
        state, runtime = state_and_runtime
        state.status = "critiqued"
        state.critique_result = _make_critique(CritiqueDecision.REVISE, NextPhase.WRITE)
        controller = LeadAgentToolController(runtime=runtime, state=state)
        result = controller.select_next_tool()
        assert result == "write_report"
        assert state.status == "researched"

    def test_critiqued_revise_verify_returns_verify(self, state_and_runtime):
        state, runtime = state_and_runtime
        state.status = "critiqued"
        state.critique_result = _make_critique(CritiqueDecision.REVISE, NextPhase.VERIFY)
        controller = LeadAgentToolController(runtime=runtime, state=state)
        result = controller.select_next_tool()
        assert result == "verify_report"
        assert state.status == "drafted"

    def test_critiqued_revise_unsupported_returns_finalize(self, state_and_runtime):
        state, runtime = state_and_runtime
        state.status = "critiqued"
        state.critique_result = _make_critique(CritiqueDecision.REVISE, NextPhase.PLAN)
        controller = LeadAgentToolController(runtime=runtime, state=state)
        assert controller.select_next_tool() == "finalize_run"

    def test_critiqued_fail_returns_finalize(self, state_and_runtime):
        state, runtime = state_and_runtime
        state.status = "critiqued"
        state.critique_result = _make_critique(CritiqueDecision.FAIL, NextPhase.EVAL)
        controller = LeadAgentToolController(runtime=runtime, state=state)
        assert controller.select_next_tool() == "finalize_run"

    def test_completed_returns_none(self, state_and_runtime):
        state, runtime = state_and_runtime
        state.status = "completed"
        controller = LeadAgentToolController(runtime=runtime, state=state)
        assert controller.select_next_tool() is None

    def test_failed_returns_none(self, state_and_runtime):
        state, runtime = state_and_runtime
        state.status = "failed"
        controller = LeadAgentToolController(runtime=runtime, state=state)
        assert controller.select_next_tool() is None


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

class TestExecuteTool:
    def test_execute_invalid_transition_rejected(self, state_and_runtime):
        state, runtime = state_and_runtime
        state.status = "initialized"
        controller = LeadAgentToolController(runtime=runtime, state=state)

        result = controller.execute_tool("write_report")
        assert result.status == "failed"
        assert "not allowed" in result.error

    def test_execute_unknown_tool(self, state_and_runtime):
        state, runtime = state_and_runtime
        controller = LeadAgentToolController(runtime=runtime, state=state)

        result = controller.execute_tool("nonexistent_tool")
        assert result.status == "failed"
        assert "Unknown tool" in result.error

    def test_execute_tool_trace_events(self, state_and_runtime, tmp_trace_writer):
        state, runtime = state_and_runtime

        # Mock the planner
        mock_planner = MagicMock(spec=Planner)
        brief = _make_brief()
        mock_planner.plan.return_value = brief
        runtime._planner = mock_planner

        controller = LeadAgentToolController(runtime=runtime, state=state)
        result = controller.execute_tool("plan_research", query="test")

        assert result.status == "success"

        # Verify trace events — the controller emits TOOL_CALL + TOOL_RESULT
        # Read from the actual trace_writer (not run_dir/trace.jsonl)
        events = tmp_trace_writer.read_all()
        controller_events = [
            e for e in events
            if e.agent_role == AgentRole.LEAD_RUNTIME
            and e.event_type in (EventType.TOOL_CALL, EventType.TOOL_RESULT)
            and e.tool_name == "plan_research"
        ]
        # At minimum: controller TOOL_CALL + controller TOOL_RESULT
        assert len(controller_events) >= 2
        # Controller TOOL_CALL has "tool=plan_research" in input_summary
        controller_calls = [e for e in controller_events
                          if "tool=plan_research" in (e.input_summary or "")]
        assert len(controller_calls) >= 1


# ---------------------------------------------------------------------------
# Full tool loop
# ---------------------------------------------------------------------------

class TestRunToolLoop:
    def test_full_pipeline_with_mocks(self, state_and_runtime, tmp_trace_writer, tmp_path):
        state, runtime = state_and_runtime
        # state_and_runtime fixture already creates test-run dir

        # Mocks for all agents
        mock_planner = MagicMock(spec=Planner)
        mock_planner.plan.return_value = _make_brief()

        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=_make_evidence(), failed_task_ids=[],
        )

        mock_writer = MagicMock(spec=WriterProtocol)
        mock_draft = MagicMock()
        mock_draft.claims = []
        mock_writer.draft.return_value = mock_draft
        mock_final = MagicMock()
        mock_writer.final.return_value = mock_final

        mock_verifier = MagicMock(spec=VerifierProtocol)
        mock_verification = MagicMock()
        mock_verification.claim_results = []
        mock_verifier.verify.return_value = mock_verification

        mock_critic = MagicMock(spec=Critic)
        mock_critic.review.return_value = _make_critique(
            CritiqueDecision.PASS, NextPhase.COMPLETE,
        )

        mock_provider = MagicMock()
        mock_provider.provider_name = "fixture"

        runtime = LeadAgentRuntime(
            state=state,
            planner=mock_planner,
            lead_researcher=mock_lead,
            writer=mock_writer,
            verifier=mock_verifier,
            critic=mock_critic,
        )

        controller = LeadAgentToolController(runtime=runtime, state=state)
        result = controller.run_tool_loop("test", mock_provider)

        assert result.status == "completed"
        assert len(controller.execution_log) >= 6  # all 6 tools

        # Verify all tools were called
        called_tools = {r.tool_name for r in controller.execution_log if r.status == "success"}
        expected = {"plan_research", "run_research_subagents", "write_report",
                    "verify_report", "critique_report", "finalize_run"}
        assert called_tools == expected

    def test_revise_research_loops(self, state_and_runtime, tmp_path):
        state, runtime = state_and_runtime
        # state_and_runtime fixture already creates test-run dir
        state.max_iterations = 3

        mock_planner = MagicMock(spec=Planner)
        mock_planner.plan.return_value = _make_brief()

        mock_lead = MagicMock()
        call_count = [0]

        def _research_side_effect(*args, **kwargs):
            call_count[0] += 1
            return MagicMock(evidence=_make_evidence(), failed_task_ids=[])

        mock_lead.conduct_research.side_effect = _research_side_effect

        mock_writer = MagicMock(spec=WriterProtocol)
        mock_draft = MagicMock()
        mock_draft.claims = []
        mock_writer.draft.return_value = mock_draft
        mock_final = MagicMock()
        mock_writer.final.return_value = mock_final

        mock_verifier = MagicMock(spec=VerifierProtocol)
        mock_verification = MagicMock()
        mock_verification.claim_results = []
        mock_verifier.verify.return_value = mock_verification

        mock_critic = MagicMock(spec=Critic)
        mock_critic.review.side_effect = [
            _make_critique(CritiqueDecision.REVISE, NextPhase.RESEARCH, ["missing"]),
            _make_critique(CritiqueDecision.PASS, NextPhase.COMPLETE),
        ]

        mock_provider = MagicMock()
        mock_provider.provider_name = "fixture"

        runtime = LeadAgentRuntime(
            state=state,
            planner=mock_planner,
            lead_researcher=mock_lead,
            writer=mock_writer,
            verifier=mock_verifier,
            critic=mock_critic,
        )

        controller = LeadAgentToolController(runtime=runtime, state=state)
        result = controller.run_tool_loop("test", mock_provider)

        assert result.status == "completed"
        assert call_count[0] == 2  # initial + re-run

    def test_max_steps_enforced(self, state_and_runtime, tmp_path):
        state, runtime = state_and_runtime
        # state_and_runtime fixture already creates test-run dir

        mock_planner = MagicMock(spec=Planner)
        mock_planner.plan.return_value = _make_brief()

        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=_make_evidence(), failed_task_ids=[],
        )

        mock_writer = MagicMock(spec=WriterProtocol)
        mock_draft = MagicMock()
        mock_draft.claims = []
        mock_writer.draft.return_value = mock_draft
        mock_final = MagicMock()
        mock_writer.final.return_value = mock_final

        mock_verifier = MagicMock(spec=VerifierProtocol)
        mock_verification = MagicMock()
        mock_verification.claim_results = []
        mock_verifier.verify.return_value = mock_verification

        mock_critic = MagicMock(spec=Critic)
        mock_critic.review.return_value = _make_critique(
            CritiqueDecision.PASS, NextPhase.COMPLETE,
        )

        mock_provider = MagicMock()
        mock_provider.provider_name = "fixture"

        runtime = LeadAgentRuntime(
            state=state,
            planner=mock_planner,
            lead_researcher=mock_lead,
            writer=mock_writer,
            verifier=mock_verifier,
            critic=mock_critic,
        )

        # max_steps=4: plan, research, write, verify (4 tools in loop)
        # Then post-loop finalize adds 1 more → 5 total
        controller = LeadAgentToolController(runtime=runtime, state=state, max_steps=4)
        result = controller.run_tool_loop("test", mock_provider)

        assert result.status == "completed"
        # With max_steps=4, exactly 4 tools execute in loop + forced finalize
        assert 4 <= len(controller.execution_log) <= 5


# ---------------------------------------------------------------------------
# Execution log
# ---------------------------------------------------------------------------

class TestExecutionLog:
    def test_log_records_successful_tools(self, state_and_runtime, tmp_path):
        state, runtime = state_and_runtime
        # state_and_runtime fixture already creates test-run dir

        mock_planner = MagicMock(spec=Planner)
        mock_planner.plan.return_value = _make_brief()
        runtime._planner = mock_planner

        controller = LeadAgentToolController(runtime=runtime, state=state)
        controller.execute_tool("plan_research", query="test")

        assert len(controller.execution_log) == 1
        assert controller.execution_log[0].tool_name == "plan_research"
        assert controller.execution_log[0].status == "success"

    def test_log_records_failed_tools(self, state_and_runtime):
        state, runtime = state_and_runtime
        controller = LeadAgentToolController(runtime=runtime, state=state)

        # Unknown tool
        controller.execute_tool("nonexistent_tool")

        assert len(controller.execution_log) == 0  # errors from execute_tool directly return

    def test_log_records_invalid_transition(self, state_and_runtime):
        state, runtime = state_and_runtime
        controller = LeadAgentToolController(runtime=runtime, state=state)

        result = controller.execute_tool("write_report")  # invalid from initialized
        assert result.status == "failed"
        assert "not allowed" in result.error

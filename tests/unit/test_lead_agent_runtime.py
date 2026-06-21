"""Unit tests for LeadAgentRuntime, RuntimeState, and RunContext."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from traceresearch.agents.lead_runtime import (
    LeadAgentRuntime,
    RunContext,
    RuntimeState,
)
from traceresearch.agents.critic import Critic
from traceresearch.agents.planner import Planner
from traceresearch.agents.verifier_protocol import VerifierProtocol
from traceresearch.agents.writer_protocol import WriterProtocol
from traceresearch.evidence.models import (
    Evidence,
    ResearchBrief,
    ResearchTask,
    ResearchRunStatus,
    SourceResult,
    SourceType,
)
from traceresearch.trace.models import AgentRole, EventType, TraceEvent, TraceStatus
from traceresearch.trace.writer import TraceWriter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_trace_writer():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield TraceWriter(Path(tmpdir) / "trace.jsonl")


@pytest.fixture
def runtime_state(tmp_trace_writer):
    return RuntimeState(
        run_id="test-run-001",
        run_dir="/tmp/test-run-001",
        trace_writer=tmp_trace_writer,
    )


@pytest.fixture
def sample_brief():
    return ResearchBrief(
        run_id="test-run-001",
        objective="Test research",
        scope_boundaries=["test"],
        assumptions=[],
        open_clarifications=[],
        perspectives=["P1", "P2"],
        success_criteria=["Complete"],
        research_tasks=[
            ResearchTask(
                research_task_id="T-001", run_id="test-run-001",
                perspective="P1", objective="Task 1", query="Q1",
            ),
            ResearchTask(
                research_task_id="T-002", run_id="test-run-001",
                perspective="P2", objective="Task 2", query="Q2",
            ),
        ],
    )


@pytest.fixture
def sample_evidence(sample_brief):
    return [
        Evidence(
            evidence_id="EV-test-run-001-001",
            run_id="test-run-001",
            research_task_id="T-001",
            perspective="P1",
            source=SourceResult(
                source_id="S-001", provider="fixture",
                title="Test Source", source_type=SourceType.BLOG,
                publisher="Test Pub", retrieved_at=datetime.now(timezone.utc),
                snippet="Test", provider_rank=1,
            ),
            authority_score=0.8, relevance_score=0.9,
            summary="Test evidence", key_points=["Point 1"],
            supported_claims=["Claim 1"], limitations=[],
        ),
    ]


# ---------------------------------------------------------------------------
# RuntimeState tests
# ---------------------------------------------------------------------------

class TestRuntimeState:
    def test_creation_defaults(self):
        state = RuntimeState(run_id="r1", run_dir="/tmp/r1")
        assert state.run_id == "r1"
        assert state.run_dir == "/tmp/r1"
        assert state.trace_writer is None
        assert state.research_brief is None
        assert state.planned_tasks == []
        assert state.evidence == []
        assert state.failed_task_ids == []
        assert state.draft_report is None
        assert state.verification_result is None
        assert state.critique_result is None
        assert state.final_report is None
        assert state.status == "initialized"

    def test_creation_with_trace_writer(self, tmp_trace_writer):
        state = RuntimeState(run_id="r1", run_dir="/tmp/r1", trace_writer=tmp_trace_writer)
        assert state.trace_writer is not None

    def test_mutable_fields(self):
        state = RuntimeState(run_id="r1", run_dir="/tmp/r1")
        state.status = "planned"
        state.evidence.append(MagicMock())
        assert state.status == "planned"
        assert len(state.evidence) == 1

    def test_run_context_is_alias(self):
        ctx = RunContext(run_id="r1", run_dir="/tmp/r1")
        assert isinstance(ctx, RuntimeState)
        assert ctx.run_id == "r1"


# ---------------------------------------------------------------------------
# LeadAgentRuntime initialization tests
# ---------------------------------------------------------------------------

class TestLeadAgentRuntimeInit:
    def test_default_construction(self, runtime_state):
        runtime = LeadAgentRuntime(state=runtime_state)
        assert runtime.state is runtime_state
        assert runtime._planner is not None
        assert runtime._lead_researcher is not None
        assert runtime._writer is not None
        assert runtime._verifier is not None
        assert runtime._critic is not None

    def test_injected_agents(self, runtime_state):
        mock_planner = MagicMock(spec=Planner)
        mock_writer = MagicMock(spec=WriterProtocol)
        mock_verifier = MagicMock(spec=VerifierProtocol)
        mock_critic = MagicMock(spec=Critic)

        runtime = LeadAgentRuntime(
            state=runtime_state,
            planner=mock_planner,
            writer=mock_writer,
            verifier=mock_verifier,
            critic=mock_critic,
        )
        assert runtime._planner is mock_planner
        assert runtime._writer is mock_writer
        assert runtime._verifier is mock_verifier
        assert runtime._critic is mock_critic


# ---------------------------------------------------------------------------
# plan_research step tests
# ---------------------------------------------------------------------------

class TestPlanResearch:
    def test_calls_planner_and_updates_state(self, runtime_state, tmp_trace_writer):
        mock_planner = MagicMock(spec=Planner)
        brief = ResearchBrief(
            run_id="test-run-001", objective="Test",
            scope_boundaries=[], assumptions=[], open_clarifications=[],
            perspectives=["P1"], success_criteria=["C1"],
            research_tasks=[
                ResearchTask(research_task_id="T-001", run_id="test-run-001",
                             perspective="P1", objective="T1", query="Q1"),
            ],
        )
        mock_planner.plan.return_value = brief

        runtime = LeadAgentRuntime(state=runtime_state, planner=mock_planner)
        result = runtime.plan_research("test query")

        mock_planner.plan.assert_called_once_with(
            run_id="test-run-001", query="test query", eval_case=None,
        )
        assert result.research_brief is brief
        assert len(result.planned_tasks) == 1
        assert result.status == "planned"

    def test_records_trace_events(self, runtime_state, tmp_trace_writer):
        mock_planner = MagicMock(spec=Planner)
        brief = ResearchBrief(
            run_id="test-run-001", objective="Test",
            scope_boundaries=[], assumptions=[], open_clarifications=[],
            perspectives=["P1"], success_criteria=["C1"],
            research_tasks=[
                ResearchTask(research_task_id="T-001", run_id="test-run-001",
                             perspective="P1", objective="T1", query="Q1"),
            ],
        )
        mock_planner.plan.return_value = brief

        runtime = LeadAgentRuntime(state=runtime_state, planner=mock_planner)
        runtime.plan_research("test query")

        events = tmp_trace_writer.read_all()
        lead_runtime_events = [e for e in events if e.agent_role == AgentRole.LEAD_RUNTIME]
        planner_events = [e for e in events if e.agent_role == AgentRole.PLANNER]

        # Should have LEAD_RUNTIME START, TOOL_CALL, TOOL_RESULT, FINISH
        assert len(lead_runtime_events) == 4
        assert all(e.tool_name == "plan_research" for e in lead_runtime_events)
        assert lead_runtime_events[0].event_type == EventType.START
        assert lead_runtime_events[1].event_type == EventType.TOOL_CALL
        assert lead_runtime_events[2].event_type == EventType.TOOL_RESULT
        assert lead_runtime_events[3].event_type == EventType.FINISH

        # Should have PLANNER START and FINISH
        assert len(planner_events) == 2
        assert planner_events[0].event_type == EventType.START
        assert planner_events[1].event_type == EventType.FINISH

    def test_needs_clarification_status(self, runtime_state, tmp_trace_writer):
        mock_planner = MagicMock(spec=Planner)
        brief = ResearchBrief(
            run_id="test-run-001", objective="Test",
            scope_boundaries=[], assumptions=[],
            open_clarifications=["Ambiguous query"],
            perspectives=[], success_criteria=[],
            research_tasks=[],
        )
        mock_planner.plan.return_value = brief

        runtime = LeadAgentRuntime(state=runtime_state, planner=mock_planner)
        result = runtime.plan_research("test query")

        assert result.status == "needs_clarification"

        events = tmp_trace_writer.read_all()
        lead_finish = [e for e in events
                       if e.agent_role == AgentRole.LEAD_RUNTIME
                       and e.event_type == EventType.FINISH]
        assert lead_finish[0].status == TraceStatus.NEEDS_CLARIFICATION

    def test_no_trace_writer_does_not_crash(self):
        state = RuntimeState(run_id="r1", run_dir="/tmp/r1")
        mock_planner = MagicMock(spec=Planner)
        brief = ResearchBrief(
            run_id="r1", objective="Test",
            scope_boundaries=[], assumptions=[], open_clarifications=[],
            perspectives=["P1"], success_criteria=["C1"],
            research_tasks=[
                ResearchTask(research_task_id="T-001", run_id="r1",
                             perspective="P1", objective="T1", query="Q1"),
            ],
        )
        mock_planner.plan.return_value = brief

        runtime = LeadAgentRuntime(state=state, planner=mock_planner)
        result = runtime.plan_research("test query")
        assert result.status == "planned"


# ---------------------------------------------------------------------------
# run_research_subagents step tests
# ---------------------------------------------------------------------------

class TestRunResearchSubagents:
    def test_calls_lead_researcher(self, runtime_state, sample_brief):
        runtime_state.research_brief = sample_brief
        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=[], failed_task_ids=[],
        )
        mock_provider = MagicMock()
        mock_provider.provider_name = "fixture"

        runtime = LeadAgentRuntime(state=runtime_state, lead_researcher=mock_lead)
        result = runtime.run_research_subagents(mock_provider, provider_tool_name="fixture.search")

        mock_lead.conduct_research.assert_called_once()
        call_kwargs = mock_lead.conduct_research.call_args.kwargs
        assert call_kwargs["brief"] is sample_brief
        assert call_kwargs["provider"] is mock_provider
        assert call_kwargs["run_id"] == "test-run-001"
        assert result.status == "researched"

    def test_records_trace_events(self, runtime_state, sample_brief, tmp_trace_writer):
        runtime_state.research_brief = sample_brief
        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=[], failed_task_ids=[],
        )
        mock_provider = MagicMock()
        mock_provider.provider_name = "fixture"

        runtime = LeadAgentRuntime(state=runtime_state, lead_researcher=mock_lead)
        runtime.run_research_subagents(mock_provider, provider_tool_name="fixture.search")

        events = tmp_trace_writer.read_all()
        lead_runtime_events = [e for e in events if e.agent_role == AgentRole.LEAD_RUNTIME]
        researcher_events = [e for e in events if e.agent_role == AgentRole.RESEARCHER]

        assert len(lead_runtime_events) == 4
        assert all(e.tool_name == "run_research_subagents" for e in lead_runtime_events)
        assert lead_runtime_events[0].event_type == EventType.START
        assert lead_runtime_events[1].event_type == EventType.TOOL_CALL
        assert lead_runtime_events[2].event_type == EventType.TOOL_RESULT
        assert lead_runtime_events[3].event_type == EventType.FINISH

        # RESEARCHER events preserved
        assert len(researcher_events) == 2

    def test_updates_state_with_evidence(self, runtime_state, sample_brief, sample_evidence):
        runtime_state.research_brief = sample_brief
        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=sample_evidence,
            failed_task_ids=["T-002"],
        )
        mock_provider = MagicMock()
        mock_provider.provider_name = "fixture"

        runtime = LeadAgentRuntime(state=runtime_state, lead_researcher=mock_lead)
        result = runtime.run_research_subagents(mock_provider)

        assert len(result.evidence) == 1
        assert result.evidence[0].evidence_id == "EV-test-run-001-001"
        assert result.failed_task_ids == ["T-002"]


# ---------------------------------------------------------------------------
# write_report step tests
# ---------------------------------------------------------------------------

class TestWriteReport:
    def test_calls_writer_draft(self, runtime_state, sample_brief, sample_evidence):
        runtime_state.research_brief = sample_brief
        runtime_state.evidence = sample_evidence
        mock_writer = MagicMock(spec=WriterProtocol)
        mock_draft = MagicMock()
        mock_draft.claims = [MagicMock(), MagicMock()]
        mock_writer.draft.return_value = mock_draft

        runtime = LeadAgentRuntime(state=runtime_state, writer=mock_writer)
        result = runtime.write_report()

        mock_writer.draft.assert_called_once_with(
            brief=sample_brief, evidence=sample_evidence,
        )
        assert result.draft_report is mock_draft
        assert result.status == "drafted"

    def test_records_trace_events(self, runtime_state, sample_brief, sample_evidence, tmp_trace_writer):
        runtime_state.research_brief = sample_brief
        runtime_state.evidence = sample_evidence
        mock_writer = MagicMock(spec=WriterProtocol)
        mock_draft = MagicMock()
        mock_draft.claims = []
        mock_writer.draft.return_value = mock_draft

        runtime = LeadAgentRuntime(state=runtime_state, writer=mock_writer)
        runtime.write_report()

        events = tmp_trace_writer.read_all()
        lead_runtime_events = [e for e in events if e.agent_role == AgentRole.LEAD_RUNTIME]
        writer_events = [e for e in events if e.agent_role == AgentRole.WRITER]

        assert len(lead_runtime_events) == 4
        assert all(e.tool_name == "write_report" for e in lead_runtime_events)
        assert len(writer_events) == 2


# ---------------------------------------------------------------------------
# verify_report step tests
# ---------------------------------------------------------------------------

class TestVerifyReport:
    def test_calls_verifier(self, runtime_state, sample_brief, sample_evidence, tmp_path):
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)
        runtime_state.research_brief = sample_brief
        runtime_state.evidence = sample_evidence
        mock_draft = MagicMock()
        mock_draft.claims = []
        runtime_state.draft_report = mock_draft

        mock_verifier = MagicMock(spec=VerifierProtocol)
        mock_verification = MagicMock()
        mock_verification.claim_results = []
        mock_verifier.verify.return_value = mock_verification

        runtime = LeadAgentRuntime(state=runtime_state, verifier=mock_verifier)
        result = runtime.verify_report()

        mock_verifier.verify.assert_called_once_with(
            run_id="test-run-001", draft=mock_draft, evidence=sample_evidence,
        )
        assert result.verification_result is mock_verification
        assert result.status == "verified"

    def test_records_trace_events(self, runtime_state, sample_brief, sample_evidence, tmp_path, tmp_trace_writer):
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)
        runtime_state.research_brief = sample_brief
        runtime_state.evidence = sample_evidence
        mock_draft = MagicMock()
        mock_draft.claims = []
        runtime_state.draft_report = mock_draft

        mock_verifier = MagicMock(spec=VerifierProtocol)
        mock_verification = MagicMock()
        mock_verification.claim_results = []
        mock_verifier.verify.return_value = mock_verification

        runtime = LeadAgentRuntime(state=runtime_state, verifier=mock_verifier)
        runtime.verify_report()

        events = tmp_trace_writer.read_all()
        lead_runtime_events = [e for e in events if e.agent_role == AgentRole.LEAD_RUNTIME]
        verifier_events = [e for e in events if e.agent_role == AgentRole.VERIFIER]

        assert len(lead_runtime_events) == 4
        assert all(e.tool_name == "verify_report" for e in lead_runtime_events)
        assert len(verifier_events) == 2


# ---------------------------------------------------------------------------
# critique_report step tests
# ---------------------------------------------------------------------------

class TestCritiqueReport:
    def test_calls_critic(self, runtime_state, sample_brief, sample_evidence, tmp_path):
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)
        runtime_state.research_brief = sample_brief
        runtime_state.evidence = sample_evidence
        mock_verification = MagicMock()
        mock_verification.claim_results = []
        runtime_state.verification_result = mock_verification
        runtime_state.failed_task_ids = []

        mock_critic = MagicMock(spec=Critic)
        mock_critique = MagicMock()
        mock_critique.decision = MagicMock()
        mock_critique.decision.value = "pass"
        mock_critic.review.return_value = mock_critique

        runtime = LeadAgentRuntime(state=runtime_state, critic=mock_critic)
        result = runtime.critique_report()

        mock_critic.review.assert_called_once()
        assert result.critique_result is mock_critique
        assert result.status == "critiqued"

    def test_records_trace_events(self, runtime_state, sample_brief, sample_evidence, tmp_path, tmp_trace_writer):
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)
        runtime_state.research_brief = sample_brief
        runtime_state.evidence = sample_evidence
        mock_verification = MagicMock()
        mock_verification.claim_results = []
        runtime_state.verification_result = mock_verification
        runtime_state.failed_task_ids = []

        mock_critic = MagicMock(spec=Critic)
        mock_critique = MagicMock()
        mock_critique.decision = MagicMock()
        mock_critique.decision.value = "pass"
        mock_critic.review.return_value = mock_critique

        runtime = LeadAgentRuntime(state=runtime_state, critic=mock_critic)
        runtime.critique_report()

        events = tmp_trace_writer.read_all()
        lead_runtime_events = [e for e in events if e.agent_role == AgentRole.LEAD_RUNTIME]
        critic_events = [e for e in events if e.agent_role == AgentRole.CRITIC]

        assert len(lead_runtime_events) == 4
        assert all(e.tool_name == "critique_report" for e in lead_runtime_events)
        assert len(critic_events) == 2


# ---------------------------------------------------------------------------
# finalize_run step tests
# ---------------------------------------------------------------------------

class TestFinalizeRun:
    def test_calls_writer_final(self, runtime_state, sample_brief, sample_evidence, tmp_path):
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)
        runtime_state.research_brief = sample_brief
        runtime_state.evidence = sample_evidence
        mock_verification = MagicMock()
        runtime_state.verification_result = mock_verification
        mock_critique = MagicMock()
        runtime_state.critique_result = mock_critique

        mock_writer = MagicMock(spec=WriterProtocol)
        mock_final = MagicMock()
        mock_writer.final.return_value = mock_final

        runtime = LeadAgentRuntime(state=runtime_state, writer=mock_writer)
        result = runtime.finalize_run()

        mock_writer.final.assert_called_once()
        assert result.final_report is mock_final
        assert result.status == "completed"

    def test_records_trace_events(self, runtime_state, sample_brief, sample_evidence, tmp_path, tmp_trace_writer):
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)
        runtime_state.research_brief = sample_brief
        runtime_state.evidence = sample_evidence
        mock_verification = MagicMock()
        runtime_state.verification_result = mock_verification
        mock_critique = MagicMock()
        runtime_state.critique_result = mock_critique

        mock_writer = MagicMock(spec=WriterProtocol)
        mock_final = MagicMock()
        mock_writer.final.return_value = mock_final

        runtime = LeadAgentRuntime(state=runtime_state, writer=mock_writer)
        runtime.finalize_run()

        events = tmp_trace_writer.read_all()
        lead_runtime_events = [e for e in events if e.agent_role == AgentRole.LEAD_RUNTIME]
        writer_events = [e for e in events if e.agent_role == AgentRole.WRITER]

        assert len(lead_runtime_events) == 4
        assert all(e.tool_name == "finalize_run" for e in lead_runtime_events)
        assert len(writer_events) == 2


# ---------------------------------------------------------------------------
# run_pipeline tests
# ---------------------------------------------------------------------------

class TestRunPipeline:
    def test_full_pipeline_flow(self, runtime_state, sample_brief, sample_evidence, tmp_path):
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)

        # Setup mocks for all agents
        mock_planner = MagicMock(spec=Planner)
        mock_planner.plan.return_value = sample_brief

        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=sample_evidence, failed_task_ids=[],
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
        mock_critique = MagicMock()
        mock_critique.decision = MagicMock()
        mock_critique.decision.value = "pass"
        mock_critic.review.return_value = mock_critique

        mock_provider = MagicMock()
        mock_provider.provider_name = "fixture"

        runtime = LeadAgentRuntime(
            state=runtime_state,
            planner=mock_planner,
            lead_researcher=mock_lead,
            writer=mock_writer,
            verifier=mock_verifier,
            critic=mock_critic,
        )

        result = runtime.run_pipeline("test query", mock_provider)

        assert result.status == "completed"
        assert result.research_brief is sample_brief
        assert result.final_report is mock_final
        mock_planner.plan.assert_called_once()
        mock_lead.conduct_research.assert_called_once()
        mock_writer.draft.assert_called_once()
        mock_verifier.verify.assert_called_once()
        mock_critic.review.assert_called_once()
        mock_writer.final.assert_called_once()

    def test_early_return_on_clarification(self, runtime_state):
        mock_planner = MagicMock(spec=Planner)
        brief = ResearchBrief(
            run_id="test-run-001", objective="Test",
            scope_boundaries=[], assumptions=[],
            open_clarifications=["ambiguous"],
            perspectives=[], success_criteria=[],
            research_tasks=[],
        )
        mock_planner.plan.return_value = brief

        runtime = LeadAgentRuntime(state=runtime_state, planner=mock_planner)
        mock_provider = MagicMock()
        result = runtime.run_pipeline("test query", mock_provider)

        assert result.status == "needs_clarification"
        # run_research_subagents should NOT have been called
        assert result.research_brief is brief

    def test_early_return_on_all_tasks_failed(self, runtime_state, sample_brief):
        mock_planner = MagicMock(spec=Planner)
        mock_planner.plan.return_value = sample_brief

        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=[], failed_task_ids=["T-001", "T-002"],
        )

        mock_provider = MagicMock()
        mock_provider.provider_name = "fixture"

        runtime = LeadAgentRuntime(
            state=runtime_state,
            planner=mock_planner,
            lead_researcher=mock_lead,
        )

        result = runtime.run_pipeline("test query", mock_provider)

        assert result.status == "failed"
        assert result.evidence == []

    def test_pipeline_trace_chain(self, runtime_state, sample_brief, sample_evidence, tmp_path, tmp_trace_writer):
        """Verify trace contains LEAD_RUNTIME events for all steps."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)

        mock_planner = MagicMock(spec=Planner)
        mock_planner.plan.return_value = sample_brief

        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=sample_evidence, failed_task_ids=[],
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
        mock_critique = MagicMock()
        mock_critique.decision = MagicMock()
        mock_critique.decision.value = "pass"
        mock_critic.review.return_value = mock_critique

        mock_provider = MagicMock()
        mock_provider.provider_name = "fixture"

        runtime = LeadAgentRuntime(
            state=runtime_state,
            planner=mock_planner,
            lead_researcher=mock_lead,
            writer=mock_writer,
            verifier=mock_verifier,
            critic=mock_critic,
        )

        runtime.run_pipeline("test query", mock_provider)

        events = tmp_trace_writer.read_all()
        lead_runtime_events = [e for e in events if e.agent_role == AgentRole.LEAD_RUNTIME]

        # 6 steps × 4 events each = 24 LEAD_RUNTIME events
        assert len(lead_runtime_events) == 24

        # Verify each step name appears
        step_names = {e.tool_name for e in lead_runtime_events}
        expected_steps = {
            "plan_research", "run_research_subagents", "write_report",
            "verify_report", "critique_report", "finalize_run",
        }
        assert step_names == expected_steps

        # Verify event types for each step
        for step_name in expected_steps:
            step_events = [e for e in lead_runtime_events if e.tool_name == step_name]
            event_types = [e.event_type for e in step_events]
            assert event_types == [
                EventType.START, EventType.TOOL_CALL,
                EventType.TOOL_RESULT, EventType.FINISH,
            ], f"Step {step_name} has wrong event types: {event_types}"

        # Verify internal agent events are also present
        planner_events = [e for e in events if e.agent_role == AgentRole.PLANNER]
        researcher_events = [e for e in events if e.agent_role == AgentRole.RESEARCHER]
        verifier_events = [e for e in events if e.agent_role == AgentRole.VERIFIER]
        critic_events = [e for e in events if e.agent_role == AgentRole.CRITIC]
        writer_events = [e for e in events if e.agent_role == AgentRole.WRITER]

        assert len(planner_events) >= 2
        assert len(researcher_events) >= 2
        assert len(verifier_events) >= 2
        assert len(critic_events) >= 2
        assert len(writer_events) >= 2


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_step_without_trace_writer_does_not_crash(self):
        """Runtime should work without a trace writer."""
        state = RuntimeState(run_id="r1", run_dir="/tmp/r1")
        mock_planner = MagicMock(spec=Planner)
        brief = ResearchBrief(
            run_id="r1", objective="Test",
            scope_boundaries=[], assumptions=[], open_clarifications=[],
            perspectives=["P1"], success_criteria=["C1"],
            research_tasks=[
                ResearchTask(research_task_id="T-001", run_id="r1",
                             perspective="P1", objective="T1", query="Q1"),
            ],
        )
        mock_planner.plan.return_value = brief

        runtime = LeadAgentRuntime(state=state, planner=mock_planner)
        result = runtime.plan_research("test query")
        assert result.status == "planned"


# ---------------------------------------------------------------------------
# AgentRole regression test
# ---------------------------------------------------------------------------

class TestAgentRoleRegression:
    def test_lead_runtime_role_exists(self):
        """LEAD_RUNTIME was added to AgentRole enum."""
        assert hasattr(AgentRole, "LEAD_RUNTIME")
        assert AgentRole.LEAD_RUNTIME == "LeadRuntime"

    def test_existing_roles_unchanged(self):
        """Existing AgentRole values are preserved."""
        assert AgentRole.PLANNER == "Planner"
        assert AgentRole.RESEARCHER == "Researcher"
        assert AgentRole.RESEARCH_LEAD == "ResearchLead"
        assert AgentRole.RESEARCH_SUBAGENT == "ResearchSubagent"
        assert AgentRole.VERIFIER == "Verifier"
        assert AgentRole.CRITIC == "Critic"
        assert AgentRole.WRITER == "Writer"
        assert AgentRole.EVAL_RUNNER == "EvalRunner"
        assert AgentRole.HARNESS == "Harness"

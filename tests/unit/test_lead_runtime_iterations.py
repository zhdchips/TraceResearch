"""Unit tests for iterative lead runtime (006) —
iteration fields, env var config, loop logic, trace events."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from traceresearch.agents.lead_runtime import (
    LeadAgentRuntime,
    RuntimeState,
    _read_max_iterations,
)
from traceresearch.agents.critic import Critic
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
    VerificationResult,
)
from traceresearch.trace.models import AgentRole, EventType, TraceEvent, TraceStatus
from traceresearch.trace.writer import TraceWriter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_critique(decision: CritiqueDecision, next_phase: NextPhase,
                   missing_perspectives=None, failed_task_ids=None) -> CritiqueResult:
    return CritiqueResult(
        run_id="test-run-001",
        missing_perspectives=missing_perspectives or [],
        weak_sources=[],
        duplicate_sections=[],
        unsupported_claims=[],
        limitations_to_add=[],
        decision=decision,
        next_phase=next_phase,
        failed_task_ids=failed_task_ids or [],
    )


def _make_brief():
    return ResearchBrief(
        run_id="test-run-001",
        objective="Test research",
        scope_boundaries=["test"],
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


# ---------------------------------------------------------------------------
# RuntimeState iteration fields
# ---------------------------------------------------------------------------

class TestRuntimeStateIterationFields:
    def test_default_iteration_fields(self):
        state = RuntimeState(run_id="r1", run_dir="/tmp/r1")
        assert state.iteration_index == 0
        assert state.max_iterations == 1
        assert state.iteration_history == []
        assert state.revision_reason is None
        assert state.next_phase is None

    def test_custom_max_iterations(self):
        state = RuntimeState(run_id="r1", run_dir="/tmp/r1", max_iterations=3)
        assert state.max_iterations == 3

    def test_iteration_history_mutable(self):
        state = RuntimeState(run_id="r1", run_dir="/tmp/r1")
        state.iteration_history.append({"iteration_index": 1, "decision": "pass"})
        assert len(state.iteration_history) == 1
        assert state.iteration_history[0]["iteration_index"] == 1


# ---------------------------------------------------------------------------
# Env var: _read_max_iterations
# ---------------------------------------------------------------------------

class TestReadMaxIterations:
    def test_default_one(self):
        assert _read_max_iterations() == 1

    def test_valid_value(self, monkeypatch):
        monkeypatch.setenv("TRACERESEARCH_MAX_RUNTIME_ITERATIONS", "5")
        assert _read_max_iterations() == 5

    def test_invalid_string_falls_back(self, monkeypatch):
        monkeypatch.setenv("TRACERESEARCH_MAX_RUNTIME_ITERATIONS", "not_a_number")
        assert _read_max_iterations() == 1

    def test_zero_falls_back(self, monkeypatch):
        monkeypatch.setenv("TRACERESEARCH_MAX_RUNTIME_ITERATIONS", "0")
        assert _read_max_iterations() == 1

    def test_negative_falls_back(self, monkeypatch):
        monkeypatch.setenv("TRACERESEARCH_MAX_RUNTIME_ITERATIONS", "-3")
        assert _read_max_iterations() == 1

    def test_empty_string_falls_back(self, monkeypatch):
        monkeypatch.setenv("TRACERESEARCH_MAX_RUNTIME_ITERATIONS", "")
        assert _read_max_iterations() == 1


# ---------------------------------------------------------------------------
# Iteration loop: PASS exits immediately
# ---------------------------------------------------------------------------

class TestIterationPass:
    def test_pass_exits_loop(self, runtime_state, tmp_trace_writer, tmp_path):
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)

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
        mock_critic.review.return_value = _make_critique(CritiqueDecision.PASS, NextPhase.COMPLETE)

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

        # With PASS, only 1 iteration
        assert result.iteration_index == 1
        assert len(result.iteration_history) == 1
        assert result.iteration_history[0]["decision"] == "pass"

        # Verify iteration trace events exist
        events = tmp_trace_writer.read_all()
        iter_events = [e for e in events if e.tool_name == "iteration_loop"]
        assert len(iter_events) >= 3  # START, TOOL_RESULT, FINISH

        # START has iter=1
        assert "iter=1" in iter_events[0].input_summary

        # TOOL_RESULT has decision=pass
        assert any("decision=pass" in e.input_summary for e in iter_events)

    def test_iteration_history_recorded(self, runtime_state, tmp_path):
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)

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
        mock_critic.review.return_value = _make_critique(CritiqueDecision.PASS, NextPhase.COMPLETE)

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
        history = result.iteration_history
        assert len(history) == 1
        assert history[0]["iteration_index"] == 1
        assert history[0]["decision"] == "pass"
        assert history[0]["next_phase"] == "complete"


# ---------------------------------------------------------------------------
# Iteration loop: REVISE with next_phase routing
# ---------------------------------------------------------------------------

class TestIterationReviseRouting:
    def test_revise_research_reruns_lead_researcher(self, runtime_state, tmp_path):
        """REVISE next_phase=research → re-runs run_research_subagents."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)
        runtime_state.max_iterations = 3

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
        # First: REVISE research, Second: PASS
        mock_critic.review.side_effect = [
            _make_critique(CritiqueDecision.REVISE, NextPhase.RESEARCH,
                           missing_perspectives=["missing P2"]),
            _make_critique(CritiqueDecision.PASS, NextPhase.COMPLETE),
        ]

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
        assert result.iteration_index == 2
        assert len(result.iteration_history) == 2

        # lead_researcher.conduct_research should be called twice (initial + re-run)
        assert mock_lead.conduct_research.call_count == 2

        # writer.draft should be called twice (iteration 1 + iteration 2)
        assert mock_writer.draft.call_count == 2

        # First iteration recorded REVISE with next_phase=research
        assert result.iteration_history[0]["decision"] == "revise"
        assert result.iteration_history[0]["next_phase"] == "research"
        assert "missing P2" in result.iteration_history[0]["revision_reason"]

        # Second iteration recorded PASS
        assert result.iteration_history[1]["decision"] == "pass"

    def test_revise_write_reruns_write(self, runtime_state, tmp_path):
        """REVISE next_phase=write → skips research, re-runs write."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)
        runtime_state.max_iterations = 3

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
        mock_critic.review.side_effect = [
            _make_critique(CritiqueDecision.REVISE, NextPhase.WRITE),
            _make_critique(CritiqueDecision.PASS, NextPhase.COMPLETE),
        ]

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
        assert result.iteration_index == 2

        # Research only called once (not re-run)
        assert mock_lead.conduct_research.call_count == 1
        # Draft called twice
        assert mock_writer.draft.call_count == 2

        assert result.iteration_history[0]["next_phase"] == "write"

    def test_revise_verify_skips_write(self, runtime_state, tmp_path):
        """REVISE next_phase=verify → skips write, re-runs verify."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)
        runtime_state.max_iterations = 3

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
        mock_critic.review.side_effect = [
            _make_critique(CritiqueDecision.REVISE, NextPhase.VERIFY),
            _make_critique(CritiqueDecision.PASS, NextPhase.COMPLETE),
        ]

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
        assert result.iteration_index == 2

        # Draft called only ONCE (verify skips write on 2nd pass)
        assert mock_writer.draft.call_count == 1
        # Verify called twice
        assert mock_verifier.verify.call_count == 2

        assert result.iteration_history[0]["next_phase"] == "verify"


# ---------------------------------------------------------------------------
# Iteration loop: max_iterations cap
# ---------------------------------------------------------------------------

class TestMaxIterationsCap:
    def test_max_iterations_1_single_pass(self, runtime_state, tmp_path):
        """max_iterations=1 → single pass, no iteration even on REVISE."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)
        runtime_state.max_iterations = 1

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
        # REVISE but max_iterations=1 → should finalize anyway
        mock_critic.review.return_value = _make_critique(
            CritiqueDecision.REVISE, NextPhase.RESEARCH,
            missing_perspectives=["missing"],
        )

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
        assert result.iteration_index == 1
        assert len(result.iteration_history) == 1
        assert result.iteration_history[0]["decision"] == "revise"

        # Only called once each
        assert mock_lead.conduct_research.call_count == 1
        assert mock_writer.draft.call_count == 1

    def test_revise_keeps_looping_until_max(self, runtime_state, tmp_path):
        """REVISE multiple times but stops at max_iterations."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)
        runtime_state.max_iterations = 4

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
        # Always REVISE — should hit max_iterations cap
        mock_critic.review.return_value = _make_critique(
            CritiqueDecision.REVISE, NextPhase.WRITE,
        )

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
        # Should exit after max_iterations=4 (not infinite loop)
        assert result.iteration_index == 4
        assert len(result.iteration_history) == 4

        # Still finalizes
        assert mock_writer.final.call_count == 1


# ---------------------------------------------------------------------------
# Iteration loop: FAIL decision
# ---------------------------------------------------------------------------

class TestIterationFail:
    def test_fail_exits_loop(self, runtime_state, tmp_path):
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)
        runtime_state.max_iterations = 3

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
        mock_critic.review.return_value = _make_critique(CritiqueDecision.FAIL, NextPhase.EVAL)

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
        assert result.iteration_index == 1
        assert result.iteration_history[0]["decision"] == "fail"


# ---------------------------------------------------------------------------
# Iteration loop: unsupported next_phase
# ---------------------------------------------------------------------------

class TestUnsupportedNextPhase:
    def test_unsupported_next_phase_warns_and_finalizes(self, runtime_state, tmp_path):
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)
        runtime_state.max_iterations = 3

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
        # REVISE with unsupported next_phase=plan
        mock_critic.review.return_value = _make_critique(
            CritiqueDecision.REVISE, NextPhase.PLAN,
        )

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
        assert result.iteration_index == 1  # only one iteration
        # Still finalizes
        assert mock_writer.final.call_count == 1


# ---------------------------------------------------------------------------
# Iteration trace events completeness
# ---------------------------------------------------------------------------

class TestIterationTrace:
    def test_iteration_events_contain_required_fields(self, runtime_state, tmp_trace_writer, tmp_path):
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)

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
        mock_critic.review.return_value = _make_critique(CritiqueDecision.PASS, NextPhase.COMPLETE)

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
        iter_events = [e for e in events if e.tool_name == "iteration_loop"]

        assert len(iter_events) == 3  # START, TOOL_RESULT, FINISH

        # All have agent_role=LEAD_RUNTIME
        for ev in iter_events:
            assert ev.agent_role == AgentRole.LEAD_RUNTIME
            assert ev.tool_name == "iteration_loop"

        # START event
        assert iter_events[0].event_type == EventType.START
        assert "iter=1" in iter_events[0].input_summary

        # TOOL_RESULT event
        assert iter_events[1].event_type == EventType.TOOL_RESULT
        assert "decision=pass" in iter_events[1].input_summary

        # FINISH event
        assert iter_events[2].event_type == EventType.FINISH

    def test_revise_iteration_trace_has_next_phase(self, runtime_state, tmp_trace_writer, tmp_path):
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)
        runtime_state.max_iterations = 2

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
        mock_critic.review.side_effect = [
            _make_critique(CritiqueDecision.REVISE, NextPhase.WRITE),
            _make_critique(CritiqueDecision.PASS, NextPhase.COMPLETE),
        ]

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
        iter_events = [e for e in events if e.tool_name == "iteration_loop"]

        # 2 iterations × 3 events each = 6 events
        # But REVISE adds an extra FINISH for the routing decision
        # Actually: START, TOOL_RESULT, FINISH per iteration
        # For REVISE iteration: START, TOOL_RESULT, FINISH(REVISE routing)
        # Total: START, TOOL_RESULT, FINISH × 2 = 6
        assert len(iter_events) >= 5

        # First iteration TOOL_RESULT should have next_phase=write
        tool_results = [e for e in iter_events if e.event_type == EventType.TOOL_RESULT]
        assert any("next_phase=write" in e.input_summary for e in tool_results)


# ---------------------------------------------------------------------------
# 005 backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_default_max_iterations_is_one(self):
        """Default max_iterations=1 preserves single-pass behavior (005 compat)."""
        state = RuntimeState(run_id="r1", run_dir="/tmp/r1")
        assert state.max_iterations == 1
        assert state.iteration_index == 0

    def test_existing_trace_events_not_broken(self, runtime_state, tmp_trace_writer, tmp_path):
        """005 step failure trace is preserved alongside iteration trace."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        runtime_state.run_dir = str(run_dir)

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
        mock_critic.review.return_value = _make_critique(CritiqueDecision.PASS, NextPhase.COMPLETE)

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
        lead_events = [e for e in events if e.agent_role == AgentRole.LEAD_RUNTIME]

        # 005: 6 steps × 4 events = 24
        # 006: + iteration events (3 for single iteration)
        # Total: 24 + 3 = 27
        step_names = {e.tool_name for e in lead_events}
        assert "plan_research" in step_names
        assert "run_research_subagents" in step_names
        assert "write_report" in step_names
        assert "verify_report" in step_names
        assert "critique_report" in step_names
        assert "finalize_run" in step_names
        assert "iteration_loop" in step_names

        # Verify each step still has expected structure
        for step_name in ["plan_research", "run_research_subagents", "write_report",
                          "verify_report", "critique_report", "finalize_run"]:
            step_events = [e for e in lead_events if e.tool_name == step_name]
            event_types = [e.event_type for e in step_events]
            assert event_types == [
                EventType.START, EventType.TOOL_CALL,
                EventType.TOOL_RESULT, EventType.FINISH,
            ], f"Step {step_name} has wrong event types: {event_types}"

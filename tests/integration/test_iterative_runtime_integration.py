"""Integration tests for the iterative lead runtime (006).

Tests the full iteration loop end-to-end with mocked agents
to verify the orchestration logic."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from traceresearch.agents.critic import Critic
from traceresearch.agents.lead_runtime import LeadAgentRuntime, RuntimeState
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

def _make_brief(run_id: str) -> ResearchBrief:
    return ResearchBrief(
        run_id=run_id,
        objective="Evaluate iteration behavior",
        scope_boundaries=["testing"],
        assumptions=[],
        open_clarifications=[],
        perspectives=["P1", "P2"],
        success_criteria=["C1"],
        research_tasks=[
            ResearchTask(
                research_task_id="T-001", run_id=run_id,
                perspective="P1", objective="Task 1", query="Q1",
            ),
            ResearchTask(
                research_task_id="T-002", run_id=run_id,
                perspective="P2", objective="Task 2", query="Q2",
            ),
        ],
    )


def _make_evidence(run_id: str) -> list[Evidence]:
    from datetime import datetime, timezone

    return [
        Evidence(
            evidence_id=f"EV-{run_id}-001",
            run_id=run_id,
            research_task_id="T-001",
            perspective="P1",
            source=SourceResult(
                source_id="S-001", provider="fixture",
                title="Source 1", source_type=SourceType.BLOG,
                publisher="Pub", retrieved_at=datetime.now(timezone.utc),
                snippet="Content", provider_rank=1,
            ),
            authority_score=0.8, relevance_score=0.9,
            summary="Evidence for P1", key_points=["K1"],
            supported_claims=["Claim 1"], limitations=[],
        ),
    ]


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestIterativeRuntimeIntegration:
    """Integration tests for iteration loop with mocked agents."""

    def test_single_iteration_with_pass(self):
        """Full pipeline with single iteration, PASS decision."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "test-run"
            run_dir.mkdir()
            trace_writer = TraceWriter(run_dir / "trace.jsonl")

            state = RuntimeState(
                run_id="int-test-pass",
                run_dir=str(run_dir),
                trace_writer=trace_writer,
                max_iterations=1,
            )

            brief = _make_brief("int-test-pass")
            evidence_items = _make_evidence("int-test-pass")

            mock_planner = MagicMock(spec=Planner)
            mock_planner.plan.return_value = brief

            mock_lead = MagicMock()
            mock_lead.conduct_research.return_value = MagicMock(
                evidence=evidence_items, failed_task_ids=[],
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
            mock_critic.review.return_value = CritiqueResult(
                run_id="int-test-pass",
                missing_perspectives=[],
                weak_sources=[],
                duplicate_sections=[],
                unsupported_claims=[],
                limitations_to_add=[],
                decision=CritiqueDecision.PASS,
                next_phase=NextPhase.COMPLETE,
                failed_task_ids=[],
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

            result = runtime.run_pipeline("test", mock_provider)

            assert result.status == "completed"
            assert result.iteration_index == 1
            assert len(result.iteration_history) == 1
            assert result.iteration_history[0]["decision"] == "pass"

            # Verify trace has iteration events
            events = trace_writer.read_all()
            iter_events = [e for e in events if e.tool_name == "iteration_loop"]
            assert len(iter_events) >= 3

    def test_multiple_iterations_max_cap(self):
        """Multiple iterations are capped at max_iterations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "test-run"
            run_dir.mkdir()
            trace_writer = TraceWriter(run_dir / "trace.jsonl")

            state = RuntimeState(
                run_id="int-test-max",
                run_dir=str(run_dir),
                trace_writer=trace_writer,
                max_iterations=5,
            )

            brief = _make_brief("int-test-max")
            evidence_items = _make_evidence("int-test-max")

            mock_planner = MagicMock(spec=Planner)
            mock_planner.plan.return_value = brief

            mock_lead = MagicMock()
            mock_lead.conduct_research.return_value = MagicMock(
                evidence=evidence_items, failed_task_ids=[],
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
            mock_critic.review.return_value = CritiqueResult(
                run_id="int-test-max",
                missing_perspectives=["P2"],
                weak_sources=[],
                duplicate_sections=[],
                unsupported_claims=[],
                limitations_to_add=[],
                decision=CritiqueDecision.REVISE,
                next_phase=NextPhase.WRITE,
                failed_task_ids=[],
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

            result = runtime.run_pipeline("test", mock_provider)
            assert result.iteration_index == 5
            assert len(result.iteration_history) == 5
            for entry in result.iteration_history:
                assert entry["decision"] == "revise"
                assert entry["next_phase"] == "write"
            assert mock_writer.final.call_count == 1

    def test_iteration_trace_chain_complete(self):
        """All phases: the trace must contain all expected event types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "test-run"
            run_dir.mkdir()
            trace_writer = TraceWriter(run_dir / "trace.jsonl")

            state = RuntimeState(
                run_id="int-test-trace",
                run_dir=str(run_dir),
                trace_writer=trace_writer,
                max_iterations=1,
            )

            brief = _make_brief("int-test-trace")
            evidence_items = _make_evidence("int-test-trace")

            mock_planner = MagicMock(spec=Planner)
            mock_planner.plan.return_value = brief

            mock_lead = MagicMock()
            mock_lead.conduct_research.return_value = MagicMock(
                evidence=evidence_items, failed_task_ids=[],
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
            mock_critic.review.return_value = CritiqueResult(
                run_id="int-test-trace",
                missing_perspectives=[],
                weak_sources=[],
                duplicate_sections=[],
                unsupported_claims=[],
                limitations_to_add=[],
                decision=CritiqueDecision.PASS,
                next_phase=NextPhase.COMPLETE,
                failed_task_ids=[],
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

            runtime.run_pipeline("test", mock_provider)

            events = trace_writer.read_all()
            lead_events = [e for e in events if e.agent_role == AgentRole.LEAD_RUNTIME]

            iter_events = [e for e in lead_events if e.tool_name == "iteration_loop"]
            assert len(iter_events) == 3  # START, TOOL_RESULT, FINISH

            step_events = [e for e in lead_events if e.tool_name != "iteration_loop"]
            assert len(step_events) == 24

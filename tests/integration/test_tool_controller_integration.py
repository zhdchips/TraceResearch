"""Integration tests for the tool controller (008).

Tests full pipeline execution with the tool controller using mocked agents."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from traceresearch.agents.critic import Critic
from traceresearch.agents.lead_runtime import LeadAgentRuntime, RuntimeState
from traceresearch.agents.lead_tool_controller import LeadAgentToolController
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


def _make_brief(run_id="test-001") -> ResearchBrief:
    return ResearchBrief(
        run_id=run_id,
        objective="Test",
        scope_boundaries=[],
        assumptions=[],
        open_clarifications=[],
        perspectives=["P1"],
        success_criteria=["C1"],
        research_tasks=[
            ResearchTask(
                research_task_id="T-001", run_id=run_id,
                perspective="P1", objective="T1", query="Q1",
            ),
        ],
    )


def _make_evidence(run_id="test-001"):
    from datetime import datetime, timezone

    return [
        Evidence(
            evidence_id=f"EV-{run_id}-001",
            run_id=run_id,
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


def _make_critique(decision, next_phase, missing=None):
    return CritiqueResult(
        run_id="test-001",
        missing_perspectives=missing or [],
        weak_sources=[],
        duplicate_sections=[],
        unsupported_claims=[],
        limitations_to_add=[],
        decision=decision,
        next_phase=next_phase,
        failed_task_ids=[],
    )


class TestToolControllerIntegration:
    def test_full_pipeline_single_pass(self):
        """Complete pipeline: all 6 tools execute, PASS → finalize."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "test-run"
            run_dir.mkdir()
            trace_writer = TraceWriter(run_dir / "trace.jsonl")

            state = RuntimeState(
                run_id="tc-int-001",
                run_dir=str(run_dir),
                trace_writer=trace_writer,
            )

            mock_planner = MagicMock(spec=Planner)
            mock_planner.plan.return_value = _make_brief("tc-int-001")

            mock_lead = MagicMock()
            mock_lead.conduct_research.return_value = MagicMock(
                evidence=_make_evidence("tc-int-001"), failed_task_ids=[],
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

            # All 6 tools should have been executed
            executed = {r.tool_name for r in controller.execution_log}
            assert executed == {
                "plan_research", "run_research_subagents",
                "write_report", "verify_report",
                "critique_report", "finalize_run",
            }

            # Trace events should include TOOL_CALL/TOOL_RESULT from controller
            events = trace_writer.read_all()
            tool_call_events = [
                e for e in events
                if e.agent_role == AgentRole.LEAD_RUNTIME
                and e.event_type == EventType.TOOL_CALL
            ]
            tool_result_events = [
                e for e in events
                if e.agent_role == AgentRole.LEAD_RUNTIME
                and e.event_type == EventType.TOOL_RESULT
            ]
            assert len(tool_call_events) >= 6
            assert len(tool_result_events) >= 6

    def test_revise_routing_all_paths(self):
        """REVISE with write → loops back correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "test-run"
            run_dir.mkdir()
            trace_writer = TraceWriter(run_dir / "trace.jsonl")

            state = RuntimeState(
                run_id="tc-int-revise",
                run_dir=str(run_dir),
                trace_writer=trace_writer,
                max_iterations=3,
            )

            mock_planner = MagicMock(spec=Planner)
            mock_planner.plan.return_value = _make_brief("tc-int-revise")

            mock_lead = MagicMock()
            mock_lead.conduct_research.return_value = MagicMock(
                evidence=_make_evidence("tc-int-revise"), failed_task_ids=[],
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
            # First: REVISE write, Second: PASS
            mock_critic.review.side_effect = [
                _make_critique(CritiqueDecision.REVISE, NextPhase.WRITE),
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
            # write_report should have been called twice
            assert mock_writer.draft.call_count == 2

    def test_trace_includes_tool_name_field(self):
        """Each TOOL_CALL/TOOL_RESULT must carry the tool_name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "test-run"
            run_dir.mkdir()
            trace_writer = TraceWriter(run_dir / "trace.jsonl")

            state = RuntimeState(
                run_id="tc-int-trace",
                run_dir=str(run_dir),
                trace_writer=trace_writer,
            )

            mock_planner = MagicMock(spec=Planner)
            mock_planner.plan.return_value = _make_brief("tc-int-trace")

            mock_lead = MagicMock()
            mock_lead.conduct_research.return_value = MagicMock(
                evidence=_make_evidence("tc-int-trace"), failed_task_ids=[],
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
            controller.run_tool_loop("test", mock_provider)

            events = trace_writer.read_all()
            controller_events = [
                e for e in events
                if e.agent_role == AgentRole.LEAD_RUNTIME
                and e.event_type in (EventType.TOOL_CALL, EventType.TOOL_RESULT)
                and "tool=" in (e.input_summary or "")
            ]
            # Should have at least 12 events (6 tools x 2 events each)
            assert len(controller_events) >= 12

            # Each should have a valid tool_name
            tool_names = {e.tool_name for e in controller_events if e.tool_name}
            expected = {
                "plan_research", "run_research_subagents",
                "write_report", "verify_report",
                "critique_report", "finalize_run",
            }
            assert tool_names == expected

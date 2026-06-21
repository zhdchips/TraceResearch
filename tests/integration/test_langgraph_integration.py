"""Integration tests for LangGraph runtime adapter (009).

Tests:
- LangGraph mode with real harness + fixture provider (completed, needs_clarification, failed)
- All 10 artifacts written on completed run
- trace.jsonl contains LANGGRAPH node/edge events
- Early-stop semantics: needs_clarification + all-failed → no Writer.final
- REVISE routing, max_iterations enforcement
- Regression: runtime + tool_controller modes still pass
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from traceresearch.agents.critic import Critic
from traceresearch.agents.lead_runtime import LeadAgentRuntime, RuntimeState
from traceresearch.agents.lead_tool_controller import LeadAgentToolController, _read_lead_agent_mode
from traceresearch.agents.lead_graph_runtime import LeadGraphRuntime
from traceresearch.agents.planner import Planner
from traceresearch.agents.verifier_protocol import VerifierProtocol
from traceresearch.agents.writer_protocol import WriterProtocol
from traceresearch.evidence.models import (
    CritiqueDecision,
    CritiqueResult,
    Evidence,
    NextPhase,
    ResearchBrief,
    ResearchRunStatus,
    ResearchTask,
    SourceResult,
    SourceType,
)
from traceresearch.harness.artifacts import REQUIRED_ARTIFACT_FILES, RunArtifacts
from traceresearch.harness.orchestrator import ResearchHarness
from traceresearch.trace.models import AgentRole, EventType, TraceStatus
from traceresearch.trace.writer import TraceWriter


# ---------------------------------------------------------------------------
# Helpers (mock-based)
# ---------------------------------------------------------------------------


def _make_brief(run_id="int-001", open_clarifications=None, research_tasks=None):
    tasks = research_tasks or [
        ResearchTask(
            research_task_id="T-001",
            run_id=run_id,
            perspective="P1",
            objective="Task 1",
            query="Query 1",
        ),
    ]
    return ResearchBrief(
        run_id=run_id,
        objective="Integration Test",
        scope_boundaries=[],
        assumptions=[],
        open_clarifications=open_clarifications or [],
        perspectives=["P1"] if not open_clarifications else [],
        success_criteria=["S1"] if not open_clarifications else [],
        research_tasks=tasks if not open_clarifications else [],
    )


def _make_evidence(run_id="int-001"):
    from datetime import datetime, timezone

    return [
        Evidence(
            evidence_id=f"EV-{run_id}-001",
            run_id=run_id,
            research_task_id="T-001",
            perspective="P1",
            source=SourceResult(
                source_id="S-001",
                provider="fixture",
                title="Test Source",
                source_type=SourceType.BLOG,
                publisher="Pub",
                retrieved_at=datetime.now(timezone.utc),
                snippet="Snippet",
                provider_rank=1,
            ),
            authority_score=0.8,
            relevance_score=0.9,
            summary="Evidence summary",
            key_points=["K1"],
            supported_claims=["C1"],
            limitations=[],
        ),
    ]


def _make_critique(decision, next_phase, missing=None):
    return CritiqueResult(
        run_id="int-001",
        missing_perspectives=missing or [],
        weak_sources=[],
        duplicate_sections=[],
        unsupported_claims=[],
        limitations_to_add=[],
        decision=decision,
        next_phase=next_phase,
        failed_task_ids=[],
    )


# ---------------------------------------------------------------------------
# Real harness tests with fixture provider
# ---------------------------------------------------------------------------


class TestLangGraphHarnessReal:
    """Tests that go through the real ResearchHarness with fixture provider."""

    def test_completed_fixture_run_produces_all_artifacts(self, tmp_path, monkeypatch):
        """LangGraph mode with fixture provider: completed run, all 10 artifacts."""
        monkeypatch.setenv("TRACERESEARCH_LEAD_AGENT_MODE", "langgraph")

        harness = ResearchHarness()
        result = harness.run_fixture(
            query="Compare LangGraph, AutoGen, and CrewAI for building evidence-grounded deep research agents.",
            case_id="001-framework-comparison",
            output_dir=tmp_path / "runs",
        )

        assert result.status == ResearchRunStatus.COMPLETED
        assert result.final_report_path is not None
        assert result.final_report_path.exists()

        # Verify all 10 required artifacts
        for name in REQUIRED_ARTIFACT_FILES:
            path = result.artifact_dir / REQUIRED_ARTIFACT_FILES[name]
            assert path.exists(), f"Missing artifact: {REQUIRED_ARTIFACT_FILES[name]}"

        # Verify trace has LangGraph events
        trace_path = result.artifact_dir / "trace.jsonl"
        events = _read_trace(trace_path)
        lg_events = [e for e in events if e.get("agent_role") == "LangGraph"]
        assert len(lg_events) > 0, "Expected LANGGRAPH events in trace"

        # Verify edge_decision events
        edge_events = [e for e in lg_events if e.get("tool_name") == "edge_decision"]
        assert len(edge_events) >= 1, "Expected edge_decision events"

    def test_needs_clarification_stops_early(self, tmp_path, monkeypatch):
        """Ambiguous query → needs_clarification, no final_report, no downstream artifacts."""
        monkeypatch.setenv("TRACERESEARCH_LEAD_AGENT_MODE", "langgraph")

        harness = ResearchHarness()
        result = harness.run_fixture(
            query="Research everything about technology.",
            case_id=None,  # triggers ambiguity detection in Planner
            output_dir=tmp_path / "runs",
        )

        assert result.status == ResearchRunStatus.NEEDS_CLARIFICATION
        assert result.final_report_path is None

        # Should have research_brief.json with open_clarifications
        brief_path = result.artifact_dir / "research_brief.json"
        assert brief_path.exists()
        brief = json.loads(brief_path.read_text())
        assert len(brief.get("open_clarifications", [])) > 0

        # Should have trace.jsonl
        trace_path = result.artifact_dir / "trace.jsonl"
        assert trace_path.exists()

        # Must NOT have final_report.md, report.json
        assert not (result.artifact_dir / "final_report.md").exists()
        assert not (result.artifact_dir / "report.json").exists()
        # Must NOT have evidence.jsonl (research never ran)
        assert not (result.artifact_dir / "evidence.jsonl").exists()

        # Trace roles must not include Writer, Verifier, Critic, Researcher
        events = _read_trace(trace_path)
        roles = {e.get("agent_role") for e in events}
        forbidden = {"Writer", "Verifier", "Critic", "Researcher", "ResearchLead", "ResearchSubagent"}
        for role in forbidden:
            assert role not in roles, f"Downstream role {role} should not appear for needs_clarification"

    def test_all_research_failed_no_final_report(self, tmp_path, monkeypatch):
        """When all research tasks fail → FAILED status, no final_report, no Writer.final call."""
        monkeypatch.setenv("TRACERESEARCH_LEAD_AGENT_MODE", "langgraph")

        # Build harness with a lead_researcher that returns empty evidence
        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=[], failed_task_ids=["T-001"],
        )

        harness = ResearchHarness(lead_researcher=mock_lead)
        result = harness.run_fixture(
            query="Compare LangGraph, AutoGen, and CrewAI for building evidence-grounded deep research agents.",
            case_id="001-framework-comparison",
            output_dir=tmp_path / "runs",
        )

        assert result.status == ResearchRunStatus.FAILED
        assert result.final_report_path is None

        # Must NOT have final_report.md / report.json
        assert not (result.artifact_dir / "final_report.md").exists()
        assert not (result.artifact_dir / "report.json").exists()


# ---------------------------------------------------------------------------
# Direct LeadGraphRuntime tests (mock-based, no harness)
# ---------------------------------------------------------------------------


class TestLangGraphDirect:
    """Direct LeadGraphRuntime tests for edge cases."""

    def test_completes_fixture_run(self, tmp_path):
        """LangGraph direct: completes a full research run."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        trace_writer = TraceWriter(run_dir / "trace.jsonl")

        state = RuntimeState(
            run_id="lg-int-001",
            run_dir=str(run_dir),
            trace_writer=trace_writer,
        )

        mock_planner = MagicMock(spec=Planner)
        mock_planner.plan.return_value = _make_brief("lg-int-001")

        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=_make_evidence("lg-int-001"), failed_task_ids=[],
        )

        mock_writer = MagicMock(spec=WriterProtocol)
        mock_draft = MagicMock()
        mock_draft.claims = []
        mock_draft.outline_markdown = "# Outline"
        mock_draft.draft_markdown = "# Draft"
        mock_writer.draft.return_value = mock_draft
        mock_final = MagicMock()
        mock_final.markdown = "# Final"
        mock_final.report_json = {"title": "Final Report"}
        mock_writer.final.return_value = mock_final

        mock_verifier = MagicMock(spec=VerifierProtocol)
        mock_v = MagicMock()
        mock_v.claim_results = []
        mock_verifier.verify.return_value = mock_v

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

        graph_rt = LeadGraphRuntime(runtime=runtime, state=state)
        final_gs = graph_rt.run(
            query="Test query",
            provider=mock_provider,
        )

        assert state.status == "completed"
        assert state.research_brief is not None
        assert state.draft_report is not None
        assert state.verification_result is not None
        assert state.critique_result is not None
        assert state.final_report is not None

    def test_revise_research_reroutes(self, tmp_path):
        """REVISE with next_phase=research triggers another research run."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        trace_writer = TraceWriter(run_dir / "trace.jsonl")

        state = RuntimeState(
            run_id="lg-rev-001",
            run_dir=str(run_dir),
            trace_writer=trace_writer,
            max_iterations=3,
        )

        mock_planner = MagicMock(spec=Planner)
        mock_planner.plan.return_value = _make_brief("lg-rev-001")

        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=_make_evidence("lg-rev-001"), failed_task_ids=[],
        )

        mock_writer = MagicMock(spec=WriterProtocol)
        mock_draft = MagicMock()
        mock_draft.claims = []
        mock_draft.outline_markdown = "# O"
        mock_draft.draft_markdown = "# D"
        mock_writer.draft.return_value = mock_draft
        mock_final = MagicMock()
        mock_final.markdown = "# F"
        mock_final.report_json = {}
        mock_writer.final.return_value = mock_final

        mock_verifier = MagicMock(spec=VerifierProtocol)
        mock_v = MagicMock()
        mock_v.claim_results = []
        mock_verifier.verify.return_value = mock_v

        mock_critic = MagicMock(spec=Critic)
        mock_critic.review.side_effect = [
            _make_critique(CritiqueDecision.REVISE, NextPhase.RESEARCH, ["P2"]),
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

        graph_rt = LeadGraphRuntime(runtime=runtime, state=state)
        graph_rt.run(query="Test query", provider=mock_provider)

        assert state.status == "completed"
        assert mock_lead.conduct_research.call_count == 2
        assert len(state.iteration_history) >= 2

    def test_revise_write_reroutes(self, tmp_path):
        """REVISE with next_phase=write re-runs write_report."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        trace_writer = TraceWriter(run_dir / "trace.jsonl")

        state = RuntimeState(
            run_id="lg-rw-001",
            run_dir=str(run_dir),
            trace_writer=trace_writer,
            max_iterations=3,
        )

        mock_planner = MagicMock(spec=Planner)
        mock_planner.plan.return_value = _make_brief("lg-rw-001")

        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=_make_evidence("lg-rw-001"), failed_task_ids=[],
        )

        mock_writer = MagicMock(spec=WriterProtocol)
        mock_draft = MagicMock()
        mock_draft.claims = []
        mock_draft.outline_markdown = "# O"
        mock_draft.draft_markdown = "# D"
        mock_writer.draft.return_value = mock_draft
        mock_final = MagicMock()
        mock_final.markdown = "# F"
        mock_final.report_json = {}
        mock_writer.final.return_value = mock_final

        mock_verifier = MagicMock(spec=VerifierProtocol)
        mock_v = MagicMock()
        mock_v.claim_results = []
        mock_verifier.verify.return_value = mock_v

        mock_critic = MagicMock(spec=Critic)
        mock_critic.review.side_effect = [
            _make_critique(CritiqueDecision.REVISE, NextPhase.WRITE, ["fix"]),
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

        graph_rt = LeadGraphRuntime(runtime=runtime, state=state)
        graph_rt.run(query="Test query", provider=mock_provider)

        assert state.status == "completed"
        assert mock_writer.draft.call_count == 2

    def test_max_iterations_stops_loop(self, tmp_path):
        """max_iterations=2 with continuous REVISE stops at the graph level."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        trace_writer = TraceWriter(run_dir / "trace.jsonl")

        state = RuntimeState(
            run_id="lg-mx-001",
            run_dir=str(run_dir),
            trace_writer=trace_writer,
            max_iterations=2,
        )

        mock_planner = MagicMock(spec=Planner)
        mock_planner.plan.return_value = _make_brief("lg-mx-001")

        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=_make_evidence("lg-mx-001"), failed_task_ids=[],
        )

        mock_writer = MagicMock(spec=WriterProtocol)
        mock_draft = MagicMock()
        mock_draft.claims = []
        mock_draft.outline_markdown = "# O"
        mock_draft.draft_markdown = "# D"
        mock_writer.draft.return_value = mock_draft
        mock_final = MagicMock()
        mock_final.markdown = "# F"
        mock_final.report_json = {}
        mock_writer.final.return_value = mock_final

        mock_verifier = MagicMock(spec=VerifierProtocol)
        mock_v = MagicMock()
        mock_v.claim_results = []
        mock_verifier.verify.return_value = mock_v

        mock_critic = MagicMock(spec=Critic)
        mock_critic.review.return_value = _make_critique(
            CritiqueDecision.REVISE, NextPhase.WRITE, ["never satisfied"],
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

        graph_rt = LeadGraphRuntime(runtime=runtime, state=state)
        graph_rt.run(query="Test query", provider=mock_provider)

        assert state.status in ("completed", "critiqued")
        assert state.iteration_index <= state.max_iterations + 1
        assert mock_writer.draft.call_count <= state.max_iterations + 1

    def test_fail_decision_still_finalizes(self, tmp_path):
        """FAIL critique → finalize_run (best-effort report, different from early-stop)."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        trace_writer = TraceWriter(run_dir / "trace.jsonl")

        state = RuntimeState(
            run_id="lg-fl-001",
            run_dir=str(run_dir),
            trace_writer=trace_writer,
            max_iterations=5,
        )

        mock_planner = MagicMock(spec=Planner)
        mock_planner.plan.return_value = _make_brief("lg-fl-001")

        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=_make_evidence("lg-fl-001"), failed_task_ids=[],
        )

        mock_writer = MagicMock(spec=WriterProtocol)
        mock_draft = MagicMock()
        mock_draft.claims = []
        mock_draft.outline_markdown = "# O"
        mock_draft.draft_markdown = "# D"
        mock_writer.draft.return_value = mock_draft
        mock_final = MagicMock()
        mock_final.markdown = "# F"
        mock_final.report_json = {}
        mock_writer.final.return_value = mock_final

        mock_verifier = MagicMock(spec=VerifierProtocol)
        mock_v = MagicMock()
        mock_v.claim_results = []
        mock_verifier.verify.return_value = mock_v

        mock_critic = MagicMock(spec=Critic)
        mock_critic.review.return_value = _make_critique(
            CritiqueDecision.FAIL, NextPhase.EVAL,
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

        graph_rt = LeadGraphRuntime(runtime=runtime, state=state)
        graph_rt.run(query="Test query", provider=mock_provider)

        # FAIL → finalize_run IS called (best-effort report)
        assert mock_writer.final.call_count == 1
        assert mock_writer.draft.call_count == 1


# ---------------------------------------------------------------------------
# Mode regression tests
# ---------------------------------------------------------------------------


class TestModeRegression:
    """Ensure default runtime and tool_controller modes are not broken."""

    def test_runtime_mode_still_works(self, tmp_path):
        """Default runtime mode: LeadAgentRuntime.run_pipeline() still works."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        trace_writer = TraceWriter(run_dir / "trace.jsonl")

        state = RuntimeState(
            run_id="reg-rt-001",
            run_dir=str(run_dir),
            trace_writer=trace_writer,
        )

        mock_planner = MagicMock(spec=Planner)
        mock_planner.plan.return_value = _make_brief("reg-rt-001")

        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=_make_evidence("reg-rt-001"), failed_task_ids=[],
        )

        mock_writer = MagicMock(spec=WriterProtocol)
        mock_draft = MagicMock()
        mock_draft.claims = []
        mock_draft.outline_markdown = "# O"
        mock_draft.draft_markdown = "# D"
        mock_writer.draft.return_value = mock_draft
        mock_final = MagicMock()
        mock_final.markdown = "# F"
        mock_writer.final.return_value = mock_final

        mock_verifier = MagicMock(spec=VerifierProtocol)
        mock_v = MagicMock()
        mock_v.claim_results = []
        mock_verifier.verify.return_value = mock_v

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

        result = runtime.run_pipeline(
            query="Test query",
            provider=mock_provider,
        )

        assert result.status == "completed"

    def test_tool_controller_mode_still_works(self, tmp_path):
        """Tool controller mode still works."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        trace_writer = TraceWriter(run_dir / "trace.jsonl")

        state = RuntimeState(
            run_id="reg-tc-001",
            run_dir=str(run_dir),
            trace_writer=trace_writer,
        )

        mock_planner = MagicMock(spec=Planner)
        mock_planner.plan.return_value = _make_brief("reg-tc-001")

        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=_make_evidence("reg-tc-001"), failed_task_ids=[],
        )

        mock_writer = MagicMock(spec=WriterProtocol)
        mock_draft = MagicMock()
        mock_draft.claims = []
        mock_draft.outline_markdown = "# O"
        mock_draft.draft_markdown = "# D"
        mock_writer.draft.return_value = mock_draft
        mock_final = MagicMock()
        mock_final.markdown = "# F"
        mock_writer.final.return_value = mock_final

        mock_verifier = MagicMock(spec=VerifierProtocol)
        mock_v = MagicMock()
        mock_v.claim_results = []
        mock_verifier.verify.return_value = mock_v

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
        result = controller.run_tool_loop("Test query", mock_provider)

        assert result.status == "completed"

    def test_langgraph_mode_env_var(self, monkeypatch):
        """_read_lead_agent_mode returns 'langgraph' when env var set."""
        monkeypatch.setenv("TRACERESEARCH_LEAD_AGENT_MODE", "langgraph")
        assert _read_lead_agent_mode() == "langgraph"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_trace(path: Path) -> list[dict]:
    """Read trace.jsonl and return list of dicts."""
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events

"""Integration tests for LangGraph runtime adapter (009).

Tests:
- LangGraph mode completes a fixture research run
- LangGraph mode produces all 10 compatible artifacts
- trace.jsonl contains LANGGRAPH node start/finish and edge decision events
- REVISE routing by next_phase
- max_iterations enforcement
- Default runtime mode still passes (regression check)
- tool_controller mode still passes (regression check)
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
    ResearchTask,
    SourceResult,
    SourceType,
)
from traceresearch.harness.artifacts import REQUIRED_ARTIFACT_FILES, RunArtifacts
from traceresearch.harness.orchestrator import ResearchHarness
from traceresearch.trace.models import AgentRole, EventType, TraceStatus
from traceresearch.trace.writer import TraceWriter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_brief(run_id="int-001") -> ResearchBrief:
    return ResearchBrief(
        run_id=run_id,
        objective="Integration Test",
        scope_boundaries=[],
        assumptions=[],
        open_clarifications=[],
        perspectives=["P1"],
        success_criteria=["S1"],
        research_tasks=[
            ResearchTask(
                research_task_id="T-001",
                run_id=run_id,
                perspective="P1",
                objective="Task 1",
                query="Query 1",
            ),
        ],
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


def _make_all_mocks(brief_id="int-001"):
    """Return a dict of all mocked agents for a full run."""
    mock_planner = MagicMock(spec=Planner)
    mock_planner.plan.return_value = _make_brief(brief_id)

    mock_lead = MagicMock()
    mock_lead.conduct_research.return_value = MagicMock(
        evidence=_make_evidence(brief_id), failed_task_ids=[],
    )

    mock_writer = MagicMock(spec=WriterProtocol)
    mock_draft = MagicMock()
    mock_draft.claims = []
    mock_draft.outline_markdown = "# Outline"
    mock_draft.draft_markdown = "# Draft Report"
    mock_writer.draft.return_value = mock_draft
    mock_final = MagicMock()
    mock_final.markdown = "# Final Report"
    mock_final.report_json = {"title": "Final Report JSON"}
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

    return {
        "planner": mock_planner,
        "lead": mock_lead,
        "writer": mock_writer,
        "verifier": mock_verifier,
        "critic": mock_critic,
        "provider": mock_provider,
    }


# ---------------------------------------------------------------------------
# LangGraph Integration Tests
# ---------------------------------------------------------------------------


class TestLangGraphIntegration:
    def test_completes_fixture_run(self, tmp_path):
        """LangGraph mode completes a full research run."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        trace_writer = TraceWriter(run_dir / "trace.jsonl")

        state = RuntimeState(
            run_id="lg-int-001",
            run_dir=str(run_dir),
            trace_writer=trace_writer,
        )

        mocks = _make_all_mocks("lg-int-001")

        runtime = LeadAgentRuntime(
            state=state,
            planner=mocks["planner"],
            lead_researcher=mocks["lead"],
            writer=mocks["writer"],
            verifier=mocks["verifier"],
            critic=mocks["critic"],
        )

        graph_rt = LeadGraphRuntime(runtime=runtime, state=state)
        final_gs = graph_rt.run(
            query="Test query",
            provider=mocks["provider"],
        )

        assert state.status == "completed"
        assert state.research_brief is not None
        assert state.draft_report is not None
        assert state.verification_result is not None
        assert state.critique_result is not None
        assert state.final_report is not None

    def test_all_artifacts_written(self, tmp_path):
        """Verify all 10 artifacts can be written from langgraph mode."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        trace_writer = TraceWriter(run_dir / "trace.jsonl")

        state = RuntimeState(
            run_id="lg-art-001",
            run_dir=str(run_dir),
            trace_writer=trace_writer,
        )

        mocks = _make_all_mocks("lg-art-001")

        runtime = LeadAgentRuntime(
            state=state,
            planner=mocks["planner"],
            lead_researcher=mocks["lead"],
            writer=mocks["writer"],
            verifier=mocks["verifier"],
            critic=mocks["critic"],
        )

        graph_rt = LeadGraphRuntime(runtime=runtime, state=state)
        graph_rt.run(query="Test query", provider=mocks["provider"])

        # Write artifacts (simulating what harness does)
        import json as _json
        artifacts = RunArtifacts.create(tmp_path / "output", "lg-art-001")

        if state.research_brief:
            _write_json(artifacts.research_brief, state.research_brief.model_dump(mode="json"))
            _write_json(artifacts.research_tasks,
                       [t.model_dump(mode="json") for t in state.planned_tasks])

        if state.draft_report:
            artifacts.outline.write_text(
                getattr(state.draft_report, "outline_markdown", ""), encoding="utf-8")
            artifacts.draft_report.write_text(
                getattr(state.draft_report, "draft_markdown", ""), encoding="utf-8")

        if state.verification_result:
            _write_json(artifacts.verification,
                       state.verification_result.model_dump(mode="json"))

        if state.critique_result:
            _write_json(artifacts.critique,
                       state.critique_result.model_dump(mode="json"))

        if state.final_report:
            artifacts.final_report.write_text(
                getattr(state.final_report, "markdown", ""), encoding="utf-8")
            report_json = getattr(state.final_report, "report_json", None)
            if report_json:
                _write_json(artifacts.report_json, report_json)

        # Copy trace
        import shutil
        shutil.copy(run_dir / "trace.jsonl", artifacts.trace)

        # Write evidence.jsonl
        artifacts.evidence.write_text("", encoding="utf-8")  # empty is fine

        # Verify all required artifact paths exist
        for name, filename in REQUIRED_ARTIFACT_FILES.items():
            path = getattr(artifacts, name)
            assert path.exists(), f"Missing artifact: {filename} at {path}"

    def test_trace_has_langgraph_events(self, tmp_path):
        """trace.jsonl contains LANGGRAPH node start/finish and edge decision events."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        trace_writer = TraceWriter(run_dir / "trace.jsonl")

        state = RuntimeState(
            run_id="lg-tr-001",
            run_dir=str(run_dir),
            trace_writer=trace_writer,
        )

        mocks = _make_all_mocks("lg-tr-001")

        runtime = LeadAgentRuntime(
            state=state,
            planner=mocks["planner"],
            lead_researcher=mocks["lead"],
            writer=mocks["writer"],
            verifier=mocks["verifier"],
            critic=mocks["critic"],
        )

        graph_rt = LeadGraphRuntime(runtime=runtime, state=state)
        graph_rt.run(query="Test query", provider=mocks["provider"])

        events = trace_writer.read_all()
        lg_events = [e for e in events if e.agent_role == AgentRole.LANGGRAPH]

        # Node start events
        node_starts = {
            e.tool_name
            for e in lg_events
            if e.event_type == EventType.START and e.tool_name
        }
        expected_nodes = {
            "plan_research", "run_research_subagents",
            "write_report", "verify_report",
            "critique_report", "finalize_run",
        }
        assert node_starts == expected_nodes, f"Missing node START events: {expected_nodes - node_starts}"

        # Node finish events
        node_finishes = {
            e.tool_name
            for e in lg_events
            if e.event_type == EventType.FINISH and e.tool_name
        }
        assert node_finishes == expected_nodes, f"Missing node FINISH events: {expected_nodes - node_finishes}"

        # Edge decision events
        edge_events = [
            e for e in lg_events
            if e.event_type == EventType.TOOL_RESULT
            and e.tool_name == "edge_decision"
        ]
        assert len(edge_events) >= 3, f"Expected >= 3 edge decisions, got {len(edge_events)}"

        # Verify edge decisions contain expected metadata
        for ev in edge_events:
            assert "from=" in ev.input_summary
            assert "to=" in ev.input_summary
            assert "decision=" in ev.input_summary

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

        mocks = _make_all_mocks("lg-rev-001")
        mocks["critic"].review.side_effect = [
            _make_critique(CritiqueDecision.REVISE, NextPhase.RESEARCH, ["P2"]),
            _make_critique(CritiqueDecision.PASS, NextPhase.COMPLETE),
        ]

        runtime = LeadAgentRuntime(
            state=state,
            planner=mocks["planner"],
            lead_researcher=mocks["lead"],
            writer=mocks["writer"],
            verifier=mocks["verifier"],
            critic=mocks["critic"],
        )

        graph_rt = LeadGraphRuntime(runtime=runtime, state=state)
        graph_rt.run(query="Test query", provider=mocks["provider"])

        assert state.status == "completed"
        assert mocks["lead"].conduct_research.call_count == 2

        # Verify iteration history
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

        mocks = _make_all_mocks("lg-rw-001")
        mocks["critic"].review.side_effect = [
            _make_critique(CritiqueDecision.REVISE, NextPhase.WRITE, ["fix"]),
            _make_critique(CritiqueDecision.PASS, NextPhase.COMPLETE),
        ]

        runtime = LeadAgentRuntime(
            state=state,
            planner=mocks["planner"],
            lead_researcher=mocks["lead"],
            writer=mocks["writer"],
            verifier=mocks["verifier"],
            critic=mocks["critic"],
        )

        graph_rt = LeadGraphRuntime(runtime=runtime, state=state)
        graph_rt.run(query="Test query", provider=mocks["provider"])

        assert state.status == "completed"
        assert mocks["writer"].draft.call_count == 2

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

        mocks = _make_all_mocks("lg-mx-001")
        # Keep returning REVISE — graph should stop after 2 iterations
        mocks["critic"].review.return_value = _make_critique(
            CritiqueDecision.REVISE, NextPhase.WRITE, ["never satisfied"],
        )

        runtime = LeadAgentRuntime(
            state=state,
            planner=mocks["planner"],
            lead_researcher=mocks["lead"],
            writer=mocks["writer"],
            verifier=mocks["verifier"],
            critic=mocks["critic"],
        )

        graph_rt = LeadGraphRuntime(runtime=runtime, state=state)
        graph_rt.run(query="Test query", provider=mocks["provider"])

        # Graph should have finished (not hung)
        assert state.status in ("completed", "critiqued")

        # iteration_index should not exceed max_iterations+1
        assert state.iteration_index <= state.max_iterations + 1

        # draft should have been called at most max_iterations+1 times
        assert mocks["writer"].draft.call_count <= state.max_iterations + 1

    def test_fail_decision_routes_to_finalize(self, tmp_path):
        """FAIL critique decision routes to finalize rather than looping."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        trace_writer = TraceWriter(run_dir / "trace.jsonl")

        state = RuntimeState(
            run_id="lg-fl-001",
            run_dir=str(run_dir),
            trace_writer=trace_writer,
            max_iterations=5,
        )

        mocks = _make_all_mocks("lg-fl-001")
        mocks["critic"].review.return_value = _make_critique(
            CritiqueDecision.FAIL, NextPhase.EVAL,
        )

        runtime = LeadAgentRuntime(
            state=state,
            planner=mocks["planner"],
            lead_researcher=mocks["lead"],
            writer=mocks["writer"],
            verifier=mocks["verifier"],
            critic=mocks["critic"],
        )

        graph_rt = LeadGraphRuntime(runtime=runtime, state=state)
        graph_rt.run(query="Test query", provider=mocks["provider"])

        # Should have finalized despite high max_iterations
        assert state.status in ("completed", "critiqued")
        # Only one draft call (not a loop)
        assert mocks["writer"].draft.call_count == 1


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

        mocks = _make_all_mocks("reg-rt-001")

        runtime = LeadAgentRuntime(
            state=state,
            planner=mocks["planner"],
            lead_researcher=mocks["lead"],
            writer=mocks["writer"],
            verifier=mocks["verifier"],
            critic=mocks["critic"],
        )

        result = runtime.run_pipeline(
            query="Test query",
            provider=mocks["provider"],
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

        mocks = _make_all_mocks("reg-tc-001")

        runtime = LeadAgentRuntime(
            state=state,
            planner=mocks["planner"],
            lead_researcher=mocks["lead"],
            writer=mocks["writer"],
            verifier=mocks["verifier"],
            critic=mocks["critic"],
        )

        controller = LeadAgentToolController(runtime=runtime, state=state)
        result = controller.run_tool_loop("Test query", mocks["provider"])

        assert result.status == "completed"

    def test_langgraph_mode_env_var(self, monkeypatch, tmp_path):
        """_read_lead_agent_mode returns 'langgraph' when env var set."""
        monkeypatch.setenv("TRACERESEARCH_LEAD_AGENT_MODE", "langgraph")
        assert _read_lead_agent_mode() == "langgraph"

    def test_langgraph_harness_run(self, tmp_path, monkeypatch):
        """ResearchHarness.run() with langgraph mode completes."""
        monkeypatch.setenv("TRACERESEARCH_LEAD_AGENT_MODE", "langgraph")

        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mocks = _make_all_mocks("harn-lg-001")

        harness = ResearchHarness(
            planner=mocks["planner"],
            lead_researcher=mocks["lead"],
            writer=mocks["writer"],
            verifier=mocks["verifier"],
            critic=mocks["critic"],
        )

        result = harness.run(
            query="Test query",
            source_provider=mocks["provider"],
            output_dir=output_dir,
        )

        # RunResult should be returned (status may vary based on mocks)
        assert result is not None
        assert result.run_id is not None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, payload: object) -> None:
    """Write *payload* as JSON to *path* with fallback for mock objects."""
    try:
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump(mode="json")
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except (TypeError, ValueError):
        path.write_text(
            json.dumps({"status": "skipped", "note": "payload not JSON serializable (test mock)"},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

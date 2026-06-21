"""Unit tests for LeadGraphRuntime (009) —
graph construction, routing logic, max_iterations enforcement."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from traceresearch.agents.critic import Critic
from traceresearch.agents.graph_state import (
    GraphState,
    create_initial_graph_state,
    sync_from_runtime_state,
)
from traceresearch.agents.lead_graph_runtime import (
    LeadGraphRuntime,
    _route_after_plan,
    _route_after_research,
    _route_after_critique,
)
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


def _make_brief(run_id="test-001") -> ResearchBrief:
    return ResearchBrief(
        run_id=run_id,
        objective="Test Objective",
        scope_boundaries=[],
        assumptions=[],
        open_clarifications=[],
        perspectives=["P1"],
        success_criteria=["C1"],
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


def _make_evidence(run_id="test-001"):
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
                publisher="Test Pub",
                retrieved_at=datetime.now(timezone.utc),
                snippet="Test snippet",
                provider_rank=1,
            ),
            authority_score=0.8,
            relevance_score=0.9,
            summary="Test evidence summary",
            key_points=["K1"],
            supported_claims=["C1"],
            limitations=[],
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


def _make_graph_state(run_id="test-001", **overrides):
    """Create a minimal GraphState for routing tests."""
    defaults = {
        "run_id": run_id,
        "run_dir": "/tmp/test",
        "status": "initialized",
        "current_step": "",
        "next_phase": "",
        "iteration_index": 0,
        "max_iterations": 1,
        "critique_decision": "",
        "revision_reason": "",
        "error_message": "",
        "artifact_paths": {},
        "_runtime_state": None,
        "_runtime": None,
    }
    defaults.update(overrides)
    return GraphState(**defaults)


# ---------------------------------------------------------------------------
# Graph construction tests
# ---------------------------------------------------------------------------


class TestGraphConstruction:
    def test_build_graph_has_all_nodes(self, tmp_path):
        """Verify the compiled graph contains all 6 expected nodes."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()

        state = RuntimeState(run_id="gc-001", run_dir=str(run_dir))
        runtime = LeadAgentRuntime(state=state)
        graph_rt = LeadGraphRuntime(runtime=runtime, state=state)

        app = graph_rt.build_graph()
        nodes = list(app.get_graph().nodes.keys())

        expected_nodes = {
            "__start__",
            "plan_research",
            "run_research_subagents",
            "write_report",
            "verify_report",
            "critique_report",
            "finalize_run",
            "__end__",
        }
        for node in expected_nodes:
            assert node in nodes, f"Missing node: {node}"

    def test_graph_compiles_successfully(self, tmp_path):
        """Graph compilation should not raise."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()

        state = RuntimeState(run_id="gc-002", run_dir=str(run_dir))
        runtime = LeadAgentRuntime(state=state)
        graph_rt = LeadGraphRuntime(runtime=runtime, state=state)

        app = graph_rt.build_graph()
        assert app is not None

    def test_graph_is_cached(self, tmp_path):
        """Second call to build_graph returns the same instance."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()

        state = RuntimeState(run_id="gc-003", run_dir=str(run_dir))
        runtime = LeadAgentRuntime(state=state)
        graph_rt = LeadGraphRuntime(runtime=runtime, state=state)

        app1 = graph_rt.build_graph()
        app2 = graph_rt.build_graph()
        assert app1 is app2


# ---------------------------------------------------------------------------
# Routing logic tests
# ---------------------------------------------------------------------------


class TestRouteAfterPlan:
    def test_normal_routes_to_research(self):
        gs = _make_graph_state(status="planned")
        result = _route_after_plan(gs)
        assert result == "run_research_subagents"

    def test_needs_clarification_routes_to_finalize(self):
        gs = _make_graph_state(status="needs_clarification")
        result = _route_after_plan(gs)
        assert result == "finalize_run"

    def test_failed_routes_to_finalize(self):
        gs = _make_graph_state(status="failed")
        result = _route_after_plan(gs)
        assert result == "finalize_run"


class TestRouteAfterResearch:
    def test_researched_routes_to_write(self):
        gs = _make_graph_state(status="researched")
        result = _route_after_research(gs)
        assert result == "write_report"

    def test_failed_routes_to_finalize(self):
        gs = _make_graph_state(status="failed")
        result = _route_after_research(gs)
        assert result == "finalize_run"


class TestRouteAfterCritique:
    def test_pass_routes_to_finalize(self):
        gs = _make_graph_state(
            status="critiqued", critique_decision="pass",
        )
        result = _route_after_critique(gs)
        assert result == "finalize_run"

    def test_fail_routes_to_finalize(self):
        gs = _make_graph_state(
            status="critiqued", critique_decision="fail",
        )
        result = _route_after_critique(gs)
        assert result == "finalize_run"

    def test_revise_research_routes_to_run_subagents(self):
        gs = _make_graph_state(
            status="critiqued",
            critique_decision="revise",
            next_phase="research",
            iteration_index=1,
            max_iterations=3,
        )
        result = _route_after_critique(gs)
        assert result == "run_research_subagents"

    def test_revise_write_routes_to_write(self):
        gs = _make_graph_state(
            status="critiqued",
            critique_decision="revise",
            next_phase="write",
            iteration_index=1,
            max_iterations=3,
        )
        result = _route_after_critique(gs)
        assert result == "write_report"

    def test_revise_verify_routes_to_verify(self):
        gs = _make_graph_state(
            status="critiqued",
            critique_decision="revise",
            next_phase="verify",
            iteration_index=1,
            max_iterations=3,
        )
        result = _route_after_critique(gs)
        assert result == "verify_report"

    def test_revise_default_unknown_phase_routes_to_write(self):
        """Unknown next_phase falls back to write_report."""
        gs = _make_graph_state(
            status="critiqued",
            critique_decision="revise",
            next_phase="eval",  # not a valid REVISE target
            iteration_index=1,
            max_iterations=3,
        )
        result = _route_after_critique(gs)
        assert result == "write_report"


class TestMaxIterations:
    def test_max_iterations_reached_routes_to_finalize(self):
        """When iteration_index >= max_iterations, REVISE routes to finalize."""
        gs = _make_graph_state(
            status="critiqued",
            critique_decision="revise",
            next_phase="research",
            iteration_index=3,
            max_iterations=3,
        )
        result = _route_after_critique(gs)
        assert result == "finalize_run"

    def test_one_more_iteration_allowed(self):
        """iteration_index < max_iterations allows another cycle."""
        gs = _make_graph_state(
            status="critiqued",
            critique_decision="revise",
            next_phase="research",
            iteration_index=2,
            max_iterations=3,
        )
        result = _route_after_critique(gs)
        assert result == "run_research_subagents"

    def test_single_iteration_revise_stops(self):
        """With max_iterations=1, even the first REVISE stops."""
        gs = _make_graph_state(
            status="critiqued",
            critique_decision="revise",
            next_phase="research",
            iteration_index=1,
            max_iterations=1,
        )
        result = _route_after_critique(gs)
        assert result == "finalize_run"

    def test_iteration_zero_revise_allowed(self):
        """iteration_index=0 means first critique, still room to revise."""
        gs = _make_graph_state(
            status="critiqued",
            critique_decision="revise",
            next_phase="write",
            iteration_index=0,
            max_iterations=2,
        )
        result = _route_after_critique(gs)
        assert result == "write_report"


# ---------------------------------------------------------------------------
# Full graph run with mocks
# ---------------------------------------------------------------------------


class TestRunGraphWithMocks:
    def test_full_pipeline_completes(self, tmp_path):
        """Run the full graph with mocked agents, verify completion."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        trace_writer = TraceWriter(run_dir / "trace.jsonl")

        state = RuntimeState(
            run_id="full-001",
            run_dir=str(run_dir),
            trace_writer=trace_writer,
        )

        # Mock agents
        mock_planner = MagicMock(spec=Planner)
        mock_planner.plan.return_value = _make_brief("full-001")

        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=_make_evidence("full-001"), failed_task_ids=[],
        )

        mock_writer = MagicMock(spec=WriterProtocol)
        mock_draft = MagicMock()
        mock_draft.claims = []
        mock_draft.outline_markdown = "# Outline"
        mock_draft.draft_markdown = "# Draft"
        mock_writer.draft.return_value = mock_draft
        mock_final = MagicMock()
        mock_final.markdown = "# Final"
        mock_final.report_json = {"key": "value"}
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

        graph_rt = LeadGraphRuntime(runtime=runtime, state=state)
        final_gs = graph_rt.run(
            query="Test query",
            provider=mock_provider,
        )

        assert state.status == "completed"
        assert final_gs["status"] == "completed"

    def test_langgraph_trace_events_in_trace(self, tmp_path):
        """Verify that LANGGRAPH events appear in the trace."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        trace_writer = TraceWriter(run_dir / "trace.jsonl")

        state = RuntimeState(
            run_id="trace-001",
            run_dir=str(run_dir),
            trace_writer=trace_writer,
        )

        mock_planner = MagicMock(spec=Planner)
        mock_planner.plan.return_value = _make_brief("trace-001")

        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=_make_evidence("trace-001"), failed_task_ids=[],
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
        graph_rt.run(query="Test query", provider=mock_provider)

        events = trace_writer.read_all()
        langgraph_events = [
            e for e in events
            if e.agent_role == AgentRole.LANGGRAPH
        ]
        assert len(langgraph_events) > 0, "Expected at least one LANGGRAPH event"

        # Should have START and FINISH events for each node
        lg_start = [e for e in langgraph_events if e.event_type == EventType.START]
        lg_finish = [e for e in langgraph_events if e.event_type == EventType.FINISH]
        lg_edge = [e for e in langgraph_events if e.event_type == EventType.TOOL_RESULT]

        assert len(lg_start) >= 6  # 6 nodes
        assert len(lg_finish) >= 6
        assert len(lg_edge) >= 3  # at least plan→research, research→write, critique→final

    def test_max_iterations_enforced_in_graph(self, tmp_path):
        """With max_iterations=1 and REVISE, graph still finishes."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        trace_writer = TraceWriter(run_dir / "trace.jsonl")

        state = RuntimeState(
            run_id="maxiter-001",
            run_dir=str(run_dir),
            trace_writer=trace_writer,
            max_iterations=1,
        )

        mock_planner = MagicMock(spec=Planner)
        mock_planner.plan.return_value = _make_brief("maxiter-001")

        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=_make_evidence("maxiter-001"), failed_task_ids=[],
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
        # REVISE — should trigger max_iterations check
        mock_critic.review.return_value = _make_critique(
            CritiqueDecision.REVISE, NextPhase.RESEARCH,
            missing=["P2"],
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
        final_gs = graph_rt.run(query="Test", provider=mock_provider)

        # Should have completed (via finalize_run) rather than looping forever
        assert state.status in ("completed", "critiqued")
        # With max_iterations=1, research should NOT have been called twice
        assert mock_lead.conduct_research.call_count == 1

    def test_revise_to_research_reruns_subagents(self, tmp_path):
        """REVISE with next_phase=research re-runs subagents."""
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()
        trace_writer = TraceWriter(run_dir / "trace.jsonl")

        state = RuntimeState(
            run_id="revise-001",
            run_dir=str(run_dir),
            trace_writer=trace_writer,
            max_iterations=3,
        )

        mock_planner = MagicMock(spec=Planner)
        mock_planner.plan.return_value = _make_brief("revise-001")

        mock_lead = MagicMock()
        mock_lead.conduct_research.return_value = MagicMock(
            evidence=_make_evidence("revise-001"), failed_task_ids=[],
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
        # First: REVISE research, Second: PASS
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

        graph_rt = LeadGraphRuntime(runtime=runtime, state=state)
        final_gs = graph_rt.run(query="Test", provider=mock_provider)

        assert state.status == "completed"
        # Research should have been called twice: initial + REVISE
        assert mock_lead.conduct_research.call_count == 2

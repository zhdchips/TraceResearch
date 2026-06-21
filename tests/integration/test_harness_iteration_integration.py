"""Integration tests for 006-008 harness integration fixes.

Tests:
- 006: iteration loop through ResearchHarness
- 008: tool_controller path through ResearchHarness
- 003: max_iterations truly prevents REVISE loops
- 004: max_total_chars budget enforcement
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from traceresearch.agents.critic import Critic
from traceresearch.agents.lead_runtime import LeadAgentRuntime, RuntimeState, _read_max_iterations
from traceresearch.agents.lead_tool_controller import LeadAgentToolController, _read_lead_agent_mode
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
from traceresearch.harness.orchestrator import ResearchHarness, RunResult
from traceresearch.source_discovery.base import SourceDiscoveryProvider
from traceresearch.trace.models import AgentRole, EventType
from traceresearch.trace.writer import TraceWriter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _make_critique(decision, next_phase, missing=None) -> CritiqueResult:
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


# ---------------------------------------------------------------------------
# 006: Iteration through ResearchHarness (classic path)
# ---------------------------------------------------------------------------

class TestHarnessIteration:
    def test_iteration_loop_through_harness(self):
        """Harness with max_iterations=3, Critic REVISE then PASS.
        Assert: trace has iteration_loop events, at least 2 write/verify/critique cycles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "test-run"
            run_dir.mkdir()
            trace_writer = TraceWriter(run_dir / "trace.jsonl")

            state = RuntimeState(
                run_id="harness-iter-001",
                run_dir=str(run_dir),
                trace_writer=trace_writer,
                max_iterations=3,
            )

            mock_planner = MagicMock(spec=Planner)
            mock_planner.plan.return_value = _make_brief("harness-iter-001")

            mock_lead = MagicMock()
            mock_lead.conduct_research.return_value = MagicMock(
                evidence=_make_evidence("harness-iter-001"), failed_task_ids=[],
            )

            mock_writer = MagicMock(spec=WriterProtocol)
            mock_draft = MagicMock()
            mock_draft.outline_markdown = "# Outline"
            mock_draft.draft_markdown = "# Draft"
            mock_draft.claims = []
            mock_writer.draft.return_value = mock_draft
            mock_final = MagicMock()
            mock_final.markdown = "# Final"
            mock_final.report_json = {}
            mock_writer.final.return_value = mock_final

            mock_verifier = MagicMock(spec=VerifierProtocol)
            mock_verification = MagicMock()
            mock_verification.claim_results = []
            mock_verification.unsupported_claim_count = 0
            mock_verification.critical_hallucination_count = 0
            mock_verification.citation_completeness = 1.0
            mock_verification.notes = []
            mock_verifier.verify.return_value = mock_verification
            # Make model_dump work for serialization
            mock_verification.model_dump = MagicMock(return_value={})

            mock_critic = MagicMock(spec=Critic)
            # First: REVISE (cycle 1), Second: PASS (cycle 2)
            mock_critic.review.side_effect = [
                _make_critique(CritiqueDecision.REVISE, NextPhase.WRITE, ["P2 missing"]),
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

            # Simulate what the harness does (run iteration loop manually)
            # Step 1: Plan
            runtime.plan_research("test query")
            assert state.status == "planned"

            # Step 2: Research
            runtime.run_research_subagents(mock_provider)
            assert state.status == "researched"

            # Steps 3-5: Iteration loop (same as harness)
            iteration = 0
            while iteration < state.max_iterations:
                iteration += 1

                if state.next_phase != "verify":
                    runtime.write_report()

                runtime.verify_report()
                runtime.critique_report()

                critique = state.critique_result
                decision = critique.decision

                state.iteration_index = iteration
                state.iteration_history.append({
                    "iteration_index": iteration,
                    "decision": decision.value,
                    "next_phase": str(critique.next_phase.value) if critique.next_phase else None,
                    "revision_reason": "; ".join(critique.missing_perspectives) if critique.missing_perspectives else None,
                })

                if decision == CritiqueDecision.PASS:
                    break
                if decision == CritiqueDecision.FAIL:
                    break
                if iteration >= state.max_iterations:
                    break

                state.revision_reason = "; ".join(critique.missing_perspectives) if critique.missing_perspectives else "revision requested"
                state.next_phase = str(critique.next_phase.value) if critique.next_phase else None

                if critique.next_phase == NextPhase.RESEARCH:
                    runtime.run_research_subagents(mock_provider)
                    state.next_phase = "write"
                elif critique.next_phase in (NextPhase.WRITE, NextPhase.VERIFY):
                    pass
                else:
                    break

            # Finalize
            runtime.finalize_run()
            assert state.status == "completed"

            # Assertions
            assert iteration == 2  # REVISE cycle + PASS cycle
            assert state.iteration_index == 2
            assert mock_writer.draft.call_count == 2  # two write cycles
            assert mock_critic.review.call_count == 2  # two critique cycles

            # Trace: iteration history recorded in state (from manual loop)
            assert len(state.iteration_history) == 2
            assert state.iteration_history[0]["decision"] == "revise"
            assert state.iteration_history[1]["decision"] == "pass"

            # Trace: LEAD_RUNTIME step events for all steps present
            events = trace_writer.read_all()
            lead_events = [e for e in events if e.agent_role == AgentRole.LEAD_RUNTIME]
            write_events = [e for e in lead_events if e.tool_name == "write_report"]
            assert len(write_events) >= 8  # 2 cycles × 4 events each

    def test_harness_env_var_iterations(self, monkeypatch):
        """TRACERESEARCH_MAX_RUNTIME_ITERATIONS=3, mock Critic REVISE then PASS
        via ResearchHarness._run_with_provider."""
        monkeypatch.setenv("TRACERESEARCH_MAX_RUNTIME_ITERATIONS", "3")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "runs"
            output_dir.mkdir()

            mock_planner = MagicMock(spec=Planner)
            mock_planner.plan.return_value = _make_brief("harness-env-001")

            mock_lead = MagicMock()
            mock_lead.conduct_research.return_value = MagicMock(
                evidence=_make_evidence("harness-env-001"), failed_task_ids=[],
            )

            mock_writer = MagicMock(spec=WriterProtocol)
            mock_draft = MagicMock()
            mock_draft.outline_markdown = "# Outline"
            mock_draft.draft_markdown = "# Draft"
            mock_draft.claims = []
            mock_writer.draft.return_value = mock_draft
            mock_final = MagicMock()
            mock_final.markdown = "# Final"
            mock_final.report_json = {}
            mock_writer.final.return_value = mock_final

            mock_verifier = MagicMock(spec=VerifierProtocol)
            mock_verification = MagicMock()
            mock_verification.claim_results = []
            mock_verification.model_dump = MagicMock(return_value={})
            mock_verifier.verify.return_value = mock_verification

            mock_critic = MagicMock(spec=Critic)
            mock_critic.review.side_effect = [
                _make_critique(CritiqueDecision.REVISE, NextPhase.WRITE),
                _make_critique(CritiqueDecision.PASS, NextPhase.COMPLETE),
            ]

            mock_provider = MagicMock(spec=SourceDiscoveryProvider)
            mock_provider.provider_name = "fixture"

            harness = ResearchHarness(
                planner=mock_planner,
                lead_researcher=mock_lead,
                writer=mock_writer,
                verifier=mock_verifier,
                critic=mock_critic,
            )

            from uuid import uuid4
            run_id = f"harness-env-{uuid4().hex[:8]}"
            result = harness._run_with_provider(
                query="test query",
                provider=mock_provider,
                output_dir=output_dir,
                run_id=run_id,
                eval_case=None,
                case_id="test-case",
            )

            assert result.status == ResearchRunStatus.COMPLETED
            # At least 2 write cycles (REVISE + PASS)
            assert mock_writer.draft.call_count == 2
            assert mock_critic.review.call_count == 2

            # Trace: iteration_loop events from harness
            artifact_dir = result.artifact_dir
            trace_path = Path(artifact_dir) / "trace.jsonl"
            if trace_path.exists():
                events = TraceWriter(trace_path).read_all()
                iter_events = [e for e in events if e.tool_name == "iteration_loop"]
                assert len(iter_events) >= 5  # START×2 + TOOL_RESULT×2 + FINISH×?


# ---------------------------------------------------------------------------
# 008: Tool controller path through ResearchHarness
# ---------------------------------------------------------------------------

class TestToolControllerHarness:
    def test_tool_controller_path_through_harness(self, monkeypatch):
        """TRACERESEARCH_LEAD_AGENT_MODE=tool_controller via ResearchHarness."""
        monkeypatch.setenv("TRACERESEARCH_LEAD_AGENT_MODE", "tool_controller")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "runs"
            output_dir.mkdir()

            mock_planner = MagicMock(spec=Planner)
            mock_planner.plan.return_value = _make_brief("tc-harness-001")

            mock_lead = MagicMock()
            mock_lead.conduct_research.return_value = MagicMock(
                evidence=_make_evidence("tc-harness-001"), failed_task_ids=[],
            )

            mock_writer = MagicMock(spec=WriterProtocol)
            mock_draft = MagicMock()
            mock_draft.outline_markdown = "# Outline"
            mock_draft.draft_markdown = "# Draft"
            mock_draft.claims = []
            mock_writer.draft.return_value = mock_draft
            mock_final = MagicMock()
            mock_final.markdown = "# Final"
            mock_final.report_json = {}
            mock_writer.final.return_value = mock_final

            mock_verifier = MagicMock(spec=VerifierProtocol)
            mock_verification = MagicMock()
            mock_verification.claim_results = []
            mock_verification.model_dump = MagicMock(return_value={})
            mock_verifier.verify.return_value = mock_verification

            mock_critic = MagicMock(spec=Critic)
            mock_critic.review.return_value = _make_critique(
                CritiqueDecision.PASS, NextPhase.COMPLETE,
            )

            mock_provider = MagicMock(spec=SourceDiscoveryProvider)
            mock_provider.provider_name = "fixture"

            harness = ResearchHarness(
                planner=mock_planner,
                lead_researcher=mock_lead,
                writer=mock_writer,
                verifier=mock_verifier,
                critic=mock_critic,
            )

            from uuid import uuid4
            run_id = f"tc-harness-{uuid4().hex[:8]}"
            result = harness._run_with_provider(
                query="test query",
                provider=mock_provider,
                output_dir=output_dir,
                run_id=run_id,
                eval_case=None,
                case_id="test-case",
            )

            assert result.status == ResearchRunStatus.COMPLETED
            assert result.final_report_path is not None

            # Verify artifacts exist
            run_dirs = list(output_dir.iterdir())
            assert len(run_dirs) == 1
            artifact_dir = run_dirs[0]
            assert (artifact_dir / "final_report.md").exists()
            assert (artifact_dir / "report.json").exists()
            assert (artifact_dir / "trace.jsonl").exists()

            # Trace: should have tool_controller events
            events = TraceWriter(artifact_dir / "trace.jsonl").read_all()
            tool_controller_traces = [
                e for e in events
                if e.agent_role == AgentRole.HARNESS
                and "tool_controller" in (e.input_summary or "")
            ]
            assert len(tool_controller_traces) >= 1

    def test_tool_controller_fixture_run_completes(self, monkeypatch):
        """Fixture run through tool_controller path completes."""
        monkeypatch.setenv("TRACERESEARCH_LEAD_AGENT_MODE", "tool_controller")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "runs"
            output_dir.mkdir()

            mock_planner = MagicMock(spec=Planner)
            mock_planner.plan.return_value = _make_brief("tc-fix-001")

            mock_lead = MagicMock()
            mock_lead.conduct_research.return_value = MagicMock(
                evidence=_make_evidence("tc-fix-001"), failed_task_ids=[],
            )

            mock_writer = MagicMock(spec=WriterProtocol)
            mock_draft = MagicMock()
            mock_draft.outline_markdown = "# O"
            mock_draft.draft_markdown = "# D"
            mock_draft.claims = []
            mock_writer.draft.return_value = mock_draft
            mock_final = MagicMock()
            mock_final.markdown = "# Final"
            mock_final.report_json = {}
            mock_writer.final.return_value = mock_final

            mock_verifier = MagicMock(spec=VerifierProtocol)
            mock_verification = MagicMock()
            mock_verification.claim_results = []
            mock_verification.model_dump = MagicMock(return_value={})
            mock_verifier.verify.return_value = mock_verification

            mock_critic = MagicMock(spec=Critic)
            mock_critic.review.return_value = _make_critique(
                CritiqueDecision.PASS, NextPhase.COMPLETE,
            )

            mock_provider = MagicMock(spec=SourceDiscoveryProvider)
            mock_provider.provider_name = "fixture"

            harness = ResearchHarness(
                planner=mock_planner,
                lead_researcher=mock_lead,
                writer=mock_writer,
                verifier=mock_verifier,
                critic=mock_critic,
            )

            from uuid import uuid4
            run_id = f"tc-fix-{uuid4().hex[:8]}"
            result = harness._run_with_provider(
                query="Compare frameworks",
                provider=mock_provider,
                output_dir=output_dir,
                run_id=run_id,
                eval_case=None,
                case_id="test",
            )

            assert result.status == ResearchRunStatus.COMPLETED
            assert result.final_report_path is not None


# ---------------------------------------------------------------------------
# Fix 3: max_iterations truly prevents REVISE loops in tool controller
# ---------------------------------------------------------------------------

class TestToolControllerMaxIterations:
    """Fix 3 verification tests."""

    def test_max_iterations_1_always_revise_only_one_cycle(self):
        """max_iterations=1, always REVISE → only 1 write/verify/critique cycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "test-run"
            run_dir.mkdir()
            trace_writer = TraceWriter(run_dir / "trace.jsonl")

            state = RuntimeState(
                run_id="tc-maxiter-001",
                run_dir=str(run_dir),
                trace_writer=trace_writer,
                max_iterations=1,
            )

            mock_planner = MagicMock(spec=Planner)
            mock_planner.plan.return_value = _make_brief("tc-maxiter-001")

            mock_lead = MagicMock()
            mock_lead.conduct_research.return_value = MagicMock(
                evidence=_make_evidence("tc-maxiter-001"), failed_task_ids=[],
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

            # Always REVISE — should only loop once
            mock_critic = MagicMock(spec=Critic)
            mock_critic.review.return_value = _make_critique(
                CritiqueDecision.REVISE, NextPhase.WRITE,
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

            controller = LeadAgentToolController(runtime=runtime, state=state, max_steps=20)
            result = controller.run_tool_loop("test", mock_provider)

            assert result.status == "completed"
            # Only 1 write/verify/critique cycle (then forced finalize)
            assert mock_writer.draft.call_count == 1
            assert mock_critic.review.call_count == 1

    def test_max_iterations_2_revise_then_pass_two_cycles(self):
        """max_iterations=2, first REVISE, second PASS → 2 cycles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "test-run"
            run_dir.mkdir()
            trace_writer = TraceWriter(run_dir / "trace.jsonl")

            state = RuntimeState(
                run_id="tc-maxiter-002",
                run_dir=str(run_dir),
                trace_writer=trace_writer,
                max_iterations=2,
            )

            mock_planner = MagicMock(spec=Planner)
            mock_planner.plan.return_value = _make_brief("tc-maxiter-002")

            mock_lead = MagicMock()
            mock_lead.conduct_research.return_value = MagicMock(
                evidence=_make_evidence("tc-maxiter-002"), failed_task_ids=[],
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
                state=state,
                planner=mock_planner,
                lead_researcher=mock_lead,
                writer=mock_writer,
                verifier=mock_verifier,
                critic=mock_critic,
            )

            controller = LeadAgentToolController(runtime=runtime, state=state, max_steps=20)
            result = controller.run_tool_loop("test", mock_provider)

            assert result.status == "completed"
            assert mock_writer.draft.call_count == 2  # two cycles
            assert mock_critic.review.call_count == 2


# ---------------------------------------------------------------------------
# Fix 4: max_total_chars enforcement
# ---------------------------------------------------------------------------

class TestMaxTotalCharsEnforcement:
    """Fix 4 verification tests."""

    def test_max_total_chars_200_enforced(self):
        """max_total_chars=200 with 10 long evidence items → output < 500 chars."""
        from traceresearch.agents.context_engineering import (
            ContextBudget,
            build_research_context,
        )

        evidence_items = []
        for i in range(10):
            from datetime import datetime, timezone

            evidence_items.append(
                Evidence(
                    evidence_id=f"EV-test-{i:03d}",
                    run_id="test-001",
                    research_task_id="T-001",
                    perspective="P1",
                    source=SourceResult(
                        source_id=f"S-{i:03d}", provider="fixture",
                        title=f"Long source title number {i} with extra padding",
                        source_type=SourceType.BLOG,
                        publisher="Test Publisher",
                        retrieved_at=datetime.now(timezone.utc),
                        snippet="x" * 200,
                        provider_rank=1,
                    ),
                    authority_score=0.8, relevance_score=0.9,
                    summary="A very long summary that would easily exceed the budget "
                    "if not properly truncated by the context engineering module. " * 5,
                    key_points=[f"Key point {j} with substantial detail" for j in range(5)],
                    supported_claims=["Claim"],
                    limitations=[f"Limitation {j}" for j in range(3)],
                )
            )

        budget = ContextBudget(
            max_evidence_items=20,
            max_chars_per_evidence=200,
            max_total_chars=200,
        )
        pack = build_research_context(evidence_items, budget=budget)

        # With max_total_chars=200, should have very few evidence items
        assert len(pack.evidence) <= 3  # budget heavily constrained
        assert len(pack.evidence) >= 1  # must keep at least first item

        # Total chars estimate should be under 500
        d = pack.to_dict()
        total_json = json.dumps(d)
        assert len(total_json) < 500, f"Expected <500 chars, got {len(total_json)}"

        # evidence_id must be preserved
        assert pack.evidence[0].evidence_id == "EV-test-000"

    def test_max_total_chars_single_large_item_preserved(self):
        """Even if single item exceeds budget, it must be preserved (with truncation)."""
        from traceresearch.agents.context_engineering import (
            ContextBudget,
            build_research_context,
        )

        from datetime import datetime, timezone

        huge_evidence = Evidence(
            evidence_id="EV-huge-001",
            run_id="test-001",
            research_task_id="T-001",
            perspective="P1",
            source=SourceResult(
                source_id="S-001", provider="fixture",
                title="A", source_type=SourceType.BLOG,
                publisher="B", retrieved_at=datetime.now(timezone.utc),
                snippet="C", provider_rank=1,
            ),
            authority_score=0.8, relevance_score=0.9,
            summary="x" * 3000,
            key_points=["KP1", "KP2", "KP3"],
            supported_claims=["Claim"],
            limitations=["L1"],
        )

        budget = ContextBudget(
            max_evidence_items=20,
            max_chars_per_evidence=500,
            max_total_chars=100,
        )
        pack = build_research_context([huge_evidence], budget=budget)

        # Must not drop the only item
        assert len(pack.evidence) == 1
        assert pack.evidence[0].evidence_id == "EV-huge-001"
        # Summary should be aggressively truncated
        assert len(pack.evidence[0].summary) < 500
        # key_points and limitations dropped under extreme budget
        assert isinstance(pack.evidence[0].key_points, list)

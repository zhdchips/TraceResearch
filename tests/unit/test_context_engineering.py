"""Unit tests for context engineering (007) —
ContextPack, EvidenceContext, CritiqueContext, builders, budget enforcement."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from traceresearch.agents.context_engineering import (
    ContextBudget,
    ContextPack,
    CritiqueContext,
    EvidenceContext,
    _compress_evidence,
    _estimate_chars,
    _truncate_text,
    build_critique_context,
    build_lead_decision_context,
    build_planning_context,
    build_research_context,
    build_verification_context,
    build_writing_context,
)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_evidence(run_id: str, count: int = 3) -> list[Evidence]:
    items = []
    for i in range(count):
        items.append(
            Evidence(
                evidence_id=f"EV-{run_id}-{i:03d}",
                run_id=run_id,
                research_task_id=f"T-{i:03d}",
                perspective=f"P{i}",
                source=SourceResult(
                    source_id=f"S-{i:03d}",
                    provider="fixture",
                    title=f"Source {i}",
                    source_type=SourceType.BLOG,
                    publisher=f"Publisher {i}",
                    retrieved_at=datetime.now(timezone.utc),
                    snippet=f"Snippet {i}",
                    provider_rank=i + 1,
                ),
                authority_score=0.8,
                relevance_score=0.9,
                summary=f"This is evidence summary number {i}." + ("x" * 200),
                key_points=[f"Key point {i}.1", f"Key point {i}.2"],
                supported_claims=[f"Claim {i}"],
                limitations=[f"Limitation {i}"],
            )
        )
    return items


def _make_critique(decision=CritiqueDecision.PASS, next_phase=NextPhase.COMPLETE) -> CritiqueResult:
    return CritiqueResult(
        run_id="test-001",
        missing_perspectives=["P-missing"],
        weak_sources=["EV-001"],
        duplicate_sections=[],
        unsupported_claims=["UC-1"],
        limitations_to_add=["Needs more sources"],
        decision=decision,
        next_phase=next_phase,
        failed_task_ids=["T-failed"],
    )


def _make_brief() -> ResearchBrief:
    return ResearchBrief(
        run_id="test-001",
        objective="Test research objective",
        scope_boundaries=["unit testing"],
        assumptions=[],
        open_clarifications=[],
        perspectives=["P1", "P2"],
        success_criteria=["C1"],
        research_tasks=[
            ResearchTask(
                research_task_id="T-001", run_id="test-001",
                perspective="P1", objective="Task 1", query="Q1",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# EvidenceContext
# ---------------------------------------------------------------------------

class TestEvidenceContext:
    def test_preserves_evidence_id(self):
        ctx = EvidenceContext(
            evidence_id="EV-001",
            source_title="Test",
            source_publisher="Pub",
            source_url="https://example.com",
            summary="Summary",
            key_points=["K1"],
            limitations=[],
        )
        assert ctx.evidence_id == "EV-001"

    def test_serializable_to_dict(self):
        ctx = EvidenceContext(
            evidence_id="EV-001",
            source_title="Test",
            source_publisher="Pub",
            source_url=None,
            summary="Summary",
            key_points=["K1"],
            limitations=["L1"],
        )
        d = ctx.to_dict()
        assert d["evidence_id"] == "EV-001"
        assert d["source_title"] == "Test"
        assert d["key_points"] == ["K1"]
        assert d["limitations"] == ["L1"]


# ---------------------------------------------------------------------------
# CritiqueContext
# ---------------------------------------------------------------------------

class TestCritiqueContext:
    def test_preserves_next_phase(self):
        ctx = CritiqueContext(
            decision="revise",
            next_phase="research",
            missing_perspectives=["P1"],
            limitations=["L1"],
            failed_task_ids=["T-1"],
        )
        assert ctx.next_phase == "research"
        assert ctx.decision == "revise"

    def test_serializable_to_dict(self):
        ctx = CritiqueContext(
            decision="pass",
            next_phase="complete",
            missing_perspectives=[],
            limitations=[],
            failed_task_ids=[],
        )
        d = ctx.to_dict()
        assert d["decision"] == "pass"
        assert d["next_phase"] == "complete"


# ---------------------------------------------------------------------------
# ContextBudget
# ---------------------------------------------------------------------------

class TestContextBudget:
    def test_defaults(self):
        b = ContextBudget()
        assert b.max_evidence_items == 20
        assert b.max_chars_per_evidence == 500
        assert b.max_total_chars == 8000

    def test_custom_values(self):
        b = ContextBudget(max_evidence_items=5, max_chars_per_evidence=100, max_total_chars=1000)
        assert b.max_evidence_items == 5
        assert b.max_chars_per_evidence == 100
        assert b.max_total_chars == 1000


# ---------------------------------------------------------------------------
# ContextPack
# ---------------------------------------------------------------------------

class TestContextPack:
    def test_default_empty(self):
        pack = ContextPack(step="planning")
        assert pack.step == "planning"
        assert pack.evidence == []
        assert pack.critique is None
        assert isinstance(pack.budget, ContextBudget)

    def test_serializable_to_dict(self):
        ev = EvidenceContext(
            evidence_id="EV-001",
            source_title="S1", source_publisher="P1", source_url=None,
            summary="Summary", key_points=["K1"], limitations=[],
        )
        critique = CritiqueContext(
            decision="pass", next_phase="complete",
            missing_perspectives=[], limitations=[], failed_task_ids=[],
        )
        pack = ContextPack(
            step="critique",
            evidence=[ev],
            critique=critique,
        )
        d = pack.to_dict()
        assert d["step"] == "critique"
        assert len(d["evidence"]) == 1
        assert d["evidence"][0]["evidence_id"] == "EV-001"
        assert d["critique"]["decision"] == "pass"


# ---------------------------------------------------------------------------
# Text truncation
# ---------------------------------------------------------------------------

class TestTruncateText:
    def test_short_text_unchanged(self):
        assert _truncate_text("hello", 100) == "hello"

    def test_long_text_truncated(self):
        result = _truncate_text("a" * 1000, 10)
        assert len(result) == 10
        assert result.endswith("…")

    def test_exact_length(self):
        result = _truncate_text("12345", 5)
        assert result == "12345"


# ---------------------------------------------------------------------------
# Character estimate
# ---------------------------------------------------------------------------

class TestEstimateChars:
    def test_empty_pack(self):
        pack = ContextPack(step="test")
        assert _estimate_chars(pack) >= len("test")

    def test_with_evidence(self):
        ev = EvidenceContext(
            evidence_id="EV-001",
            source_title="Source", source_publisher="Pub", source_url="http://x",
            summary="A summary", key_points=["KP1"], limitations=[],
        )
        pack = ContextPack(step="research", evidence=[ev])
        est = _estimate_chars(pack)
        assert est > 0


# ---------------------------------------------------------------------------
# Evidence compression
# ---------------------------------------------------------------------------

class TestCompressEvidence:
    def test_max_evidence_items_cap(self):
        evidence = _make_evidence("test", count=10)
        budget = ContextBudget(max_evidence_items=3)
        result = _compress_evidence(evidence, budget)
        assert len(result) == 3

    def test_summary_truncation(self):
        evidence = _make_evidence("test", count=1)
        evidence[0].summary = "x" * 1000
        budget = ContextBudget(max_chars_per_evidence=50)
        result = _compress_evidence(evidence, budget)
        assert len(result[0].summary) <= 50
        assert result[0].summary.endswith("…")

    def test_preserves_evidence_id(self):
        evidence = _make_evidence("test", count=3)
        result = _compress_evidence(evidence, ContextBudget())
        ids = [e.evidence_id for e in result]
        assert "EV-test-000" in ids
        assert "EV-test-001" in ids
        assert "EV-test-002" in ids


# ---------------------------------------------------------------------------
# Context pack builders
# ---------------------------------------------------------------------------

class TestBuildPlanningContext:
    def test_builds_empty_planning_pack(self):
        pack = build_planning_context(None)
        assert pack.step == "planning"
        assert pack.evidence == []

    def test_builds_with_brief(self):
        brief = _make_brief()
        pack = build_planning_context(brief)
        assert pack.metadata["objective"] == "Test research objective"
        assert pack.metadata["perspectives"] == ["P1", "P2"]


class TestBuildResearchContext:
    def test_builds_with_evidence(self):
        evidence = _make_evidence("test", count=3)
        pack = build_research_context(evidence)
        assert pack.step == "research"
        assert len(pack.evidence) == 3
        assert pack.metadata["total_evidence"] == 3

    def test_respects_budget(self):
        evidence = _make_evidence("test", count=10)
        budget = ContextBudget(max_evidence_items=2)
        pack = build_research_context(evidence, budget=budget)
        assert len(pack.evidence) == 2


class TestBuildWritingContext:
    def test_builds_with_evidence_and_draft(self):
        evidence = _make_evidence("test", count=2)
        pack = build_writing_context(evidence)
        assert pack.step == "writing"
        assert len(pack.evidence) == 2
        assert pack.metadata["has_draft"] is False


class TestBuildVerificationContext:
    def test_builds_with_verification(self):
        evidence = _make_evidence("test", count=2)
        verification = VerificationResult(
            run_id="test-001",
            checked_at=datetime.now(timezone.utc),
            claim_results=[],
            unsupported_claim_count=1,
            critical_hallucination_count=0,
            citation_completeness=0.9,
            notes=[],
        )
        pack = build_verification_context(verification, evidence)
        assert pack.step == "verification"
        assert pack.metadata["unsupported_claims"] == 1
        assert len(pack.evidence) == 2


class TestBuildCritiqueContext:
    def test_preserves_critique_decision_and_next_phase(self):
        critique = _make_critique(CritiqueDecision.REVISE, NextPhase.RESEARCH)
        pack = build_critique_context(critique)
        assert pack.step == "critique"
        assert pack.critique is not None
        assert pack.critique.decision == "revise"
        assert pack.critique.next_phase == "research"
        assert "P-missing" in pack.critique.missing_perspectives
        assert "Needs more sources" in pack.critique.limitations
        assert "T-failed" in pack.critique.failed_task_ids

    def test_none_critique(self):
        pack = build_critique_context(None)
        assert pack.critique is None

    def test_preserves_missing_perspectives(self):
        critique = _make_critique(CritiqueDecision.REVISE, NextPhase.WRITE)
        pack = build_critique_context(critique)
        assert "P-missing" in pack.critique.missing_perspectives

    def test_preserves_weak_sources_as_limitations(self):
        critique = _make_critique(CritiqueDecision.PASS, NextPhase.COMPLETE)
        pack = build_critique_context(critique)
        assert pack.critique.limitations == ["Needs more sources"]


class TestBuildLeadDecisionContext:
    def test_builds_from_runtime_state(self):
        from traceresearch.agents.lead_runtime import RuntimeState

        state = RuntimeState(run_id="test-001", run_dir="/tmp/test")
        state.evidence = _make_evidence("test", count=2)
        state.critique_result = _make_critique(CritiqueDecision.REVISE, NextPhase.WRITE)
        state.status = "verified"
        state.iteration_index = 2

        pack = build_lead_decision_context(state)
        assert pack.step == "decision"
        assert len(pack.evidence) == 2
        assert pack.critique is not None
        assert pack.critique.decision == "revise"
        assert pack.critique.next_phase == "write"
        assert pack.metadata["status"] == "verified"
        assert pack.metadata["iteration_index"] == 2

    def test_state_without_critique(self):
        from traceresearch.agents.lead_runtime import RuntimeState

        state = RuntimeState(run_id="test-001", run_dir="/tmp/test")
        state.evidence = _make_evidence("test", count=1)

        pack = build_lead_decision_context(state)
        assert pack.critique is None
        assert len(pack.evidence) == 1


# ---------------------------------------------------------------------------
# Budget enforcement
# ---------------------------------------------------------------------------

class TestBudgetEnforcement:
    def test_max_evidence_items_respected(self):
        evidence = _make_evidence("test", count=50)
        budget = ContextBudget(max_evidence_items=5)
        pack = build_research_context(evidence, budget=budget)
        assert len(pack.evidence) == 5

    def test_long_text_truncated_in_context_pack(self):
        evidence = _make_evidence("test", count=1)
        evidence[0].summary = "A" * 2000
        budget = ContextBudget(max_chars_per_evidence=100)
        pack = build_research_context(evidence, budget=budget)
        assert len(pack.evidence[0].summary) <= 100

    def test_limitations_not_dropped(self):
        evidence = _make_evidence("test", count=1)
        evidence[0].limitations = [
            "L1", "L2", "L3", "L4", "L5", "L6", "L7",
        ]
        pack = build_research_context(evidence)
        # key_points and limitations are capped at 5 each
        assert len(pack.evidence[0].limitations) == 5


# ---------------------------------------------------------------------------
# RuntimeState compatibility
# ---------------------------------------------------------------------------

class TestRuntimeStateContextField:
    def test_latest_context_pack_field_exists(self):
        from traceresearch.agents.lead_runtime import RuntimeState

        state = RuntimeState(run_id="r1", run_dir="/tmp/r1")
        assert state.latest_context_pack is None

    def test_latest_context_pack_settable(self):
        from traceresearch.agents.lead_runtime import RuntimeState

        state = RuntimeState(run_id="r1", run_dir="/tmp/r1")
        pack = ContextPack(step="test")
        state.latest_context_pack = pack
        assert state.latest_context_pack is pack
        assert state.latest_context_pack.step == "test"

"""Tests for LLMWriter — mock LLMProvider, no real LLM calls."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import BaseModel

from traceresearch.agents.llm_writer import LLMWriter
from traceresearch.agents.writer import DraftReport, FinalReport, Writer
from traceresearch.agents.writer_protocol import WriterProtocol
from traceresearch.evidence.models import (
    Claim,
    ClaimSupportStatus,
    CritiqueDecision,
    CritiqueResult,
    Evidence,
    EvidenceStatus,
    NextPhase,
    ResearchBrief,
    ResearchTask,
    ResearchTaskStatus,
    SourceResult,
    SourceType,
    VerificationResult,
)
from traceresearch.llm.provider import LLMProvider, LLMProviderError
from traceresearch.llm.schemas import (
    LLMFinalReportSchema,
    LLMFindingSchema,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeWriterProvider(LLMProvider):
    """Returns a pre-built LLMFinalReportSchema."""

    def __init__(self, report: LLMFinalReportSchema) -> None:
        self._report = report

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return "fake-model"

    def complete(
        self,
        prompt: str,
        response_schema: type[BaseModel],
        system_prompt: str | None = None,
    ) -> BaseModel:
        if response_schema is not LLMFinalReportSchema:
            raise LLMProviderError("invalid_response", "fake", "fake-model", 0)
        return self._report


class _FailingWriterProvider(LLMProvider):
    """Always raises LLMProviderError."""

    def __init__(self, reason: str = "provider_error") -> None:
        self._reason = reason

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return "fake-model"

    def complete(
        self,
        prompt: str,
        response_schema: type[BaseModel],
        system_prompt: str | None = None,
    ) -> BaseModel:
        raise LLMProviderError(self._reason, "fake", "fake-model", 100)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_brief(run_id: str = "test-run") -> ResearchBrief:
    return ResearchBrief(
        run_id=run_id,
        objective="Test objective.",
        scope_boundaries=["scope"],
        assumptions=["a"],
        open_clarifications=[],
        perspectives=["p1"],
        success_criteria=["sc1"],
        research_tasks=[
            ResearchTask(
                research_task_id="T1",
                run_id=run_id,
                perspective="p1",
                objective="obj",
                query="q",
            )
        ],
    )


def _make_source(source_id: str) -> SourceResult:
    return SourceResult(
        source_id=source_id,
        provider="fixture",
        title=f"Source {source_id}",
        source_type=SourceType.BLOG,
        retrieved_at=datetime.now(timezone.utc),
        snippet="snippet",
        provider_rank=1,
    )


def _make_evidence(evidence_id: str, run_id: str = "test-run") -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        run_id=run_id,
        research_task_id="T1",
        perspective="p1",
        source=_make_source(f"S-{evidence_id}"),
        authority_score=0.8,
        relevance_score=0.9,
        summary=f"Summary of {evidence_id}.",
        key_points=["key point"],
        supported_claims=[f"Claim about {evidence_id}"],
        limitations=[],
        status=EvidenceStatus.VERIFIED,
        verification_notes=["ok"],
    )


def _make_verification(run_id: str = "test-run") -> VerificationResult:
    return VerificationResult(
        run_id=run_id,
        checked_at=datetime.now(timezone.utc),
        claim_results=[
            Claim(
                claim_id="CL-001",
                run_id=run_id,
                text="Claim text",
                section_id="findings",
                evidence_ids=["EVID-001"],
                support_status=ClaimSupportStatus.SUPPORTED,
            )
        ],
        unsupported_claim_count=0,
        critical_hallucination_count=0,
        citation_completeness=1.0,
    )


def _make_critique(run_id: str = "test-run") -> CritiqueResult:
    return CritiqueResult(
        run_id=run_id,
        missing_perspectives=[],
        weak_sources=[],
        duplicate_sections=[],
        unsupported_claims=[],
        limitations_to_add=[],
        decision=CritiqueDecision.PASS,
        next_phase=NextPhase.COMPLETE,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLLMWriterSuccess:
    def test_implements_writer_protocol(self):
        provider = _FakeWriterProvider(
            LLMFinalReportSchema(
                executive_summary="Summary.",
                findings=[LLMFindingSchema(text="F1", evidence_ids=["EVID-001"], confidence="high")],
                limitations=["Limited."],
                evidence_references=["EVID-001: Source"],
                follow_up_questions=["Q1"],
            )
        )
        w = LLMWriter(provider)
        assert isinstance(w, WriterProtocol)

    def test_final_returns_final_report_with_evidence_ids(self):
        provider = _FakeWriterProvider(
            LLMFinalReportSchema(
                executive_summary="Summary text.",
                findings=[
                    LLMFindingSchema(text="Finding A", evidence_ids=["EVID-001"], confidence="high"),
                    LLMFindingSchema(text="Finding B", evidence_ids=["EVID-001", "EVID-002"], confidence="medium"),
                ],
                limitations=["Limitation 1"],
                evidence_references=["EVID-001: Src A", "EVID-002: Src B"],
                follow_up_questions=["What about X?"],
            )
        )
        w = LLMWriter(provider)
        result = w.final(
            brief=_make_brief(),
            verified_evidence=[_make_evidence("EVID-001"), _make_evidence("EVID-002")],
            verification=_make_verification(),
            critique=_make_critique(),
        )
        assert isinstance(result, FinalReport)
        assert "Finding A" in result.markdown
        assert "Finding B" in result.markdown
        assert "EVID-001" in result.markdown
        assert "Limitation 1" in result.markdown

    def test_empty_evidence_produces_no_findings_report(self):
        provider = _FakeWriterProvider(
            LLMFinalReportSchema(
                executive_summary="No verified findings available.",
                findings=[],
                limitations=["No data."],
                evidence_references=[],
                follow_up_questions=["Expand scope?"],
            )
        )
        w = LLMWriter(provider)
        result = w.final(
            brief=_make_brief(),
            verified_evidence=[],
            verification=_make_verification(),
            critique=_make_critique(),
        )
        assert isinstance(result, FinalReport)
        assert "No verified findings" in result.markdown or "no verified" in result.markdown.lower()

    def test_draft_delegates_to_deterministic_writer(self):
        """LLMWriter.draft() should use deterministic Writer for draft generation."""
        provider = _FakeWriterProvider(
            LLMFinalReportSchema(
                executive_summary="S", findings=[], limitations=[], evidence_references=[], follow_up_questions=[],
            )
        )
        w = LLMWriter(provider)
        brief = _make_brief()
        evidence = [_make_evidence("EVID-001")]
        draft = w.draft(brief=brief, evidence=evidence)
        assert isinstance(draft, DraftReport)
        assert draft.outline_markdown
        assert draft.claims


class TestLLMWriterFallback:
    def test_falls_back_deterministic_on_invalid_json(self):
        """LLM returns non-parseable output → fallback deterministic Writer."""

        class _BrokenWriterProvider(LLMProvider):
            @property
            def provider_name(self) -> str:
                return "broken"
            @property
            def model(self) -> str:
                return "broken"
            def complete(self, prompt, response_schema, system_prompt=None):
                return response_schema.model_validate_json("{bad json")

        w = LLMWriter(_BrokenWriterProvider(), fallback_on_failure=True)
        result = w.final(
            brief=_make_brief(),
            verified_evidence=[_make_evidence("EVID-001")],
            verification=_make_verification(),
            critique=_make_critique(),
        )
        assert isinstance(result, FinalReport)
        # Deterministic fallback produces standard report sections
        assert "Executive Summary" in result.markdown

    def test_falls_back_on_llm_provider_error(self):
        w = LLMWriter(_FailingWriterProvider("timeout"), fallback_on_failure=True)
        result = w.final(
            brief=_make_brief(),
            verified_evidence=[_make_evidence("EVID-001")],
            verification=_make_verification(),
            critique=_make_critique(),
        )
        assert isinstance(result, FinalReport)
        assert "Executive Summary" in result.markdown

    def test_falls_back_on_hallucinated_evidence_id(self):
        """LLM returns an evidence_id not in the input set → fallback deterministic."""
        provider = _FakeWriterProvider(
            LLMFinalReportSchema(
                executive_summary="Summary.",
                findings=[
                    LLMFindingSchema(
                        text="Finding",
                        evidence_ids=["EVID-HALLUCINATED"],  # not in input!
                        confidence="high",
                    )
                ],
                limitations=[],
                evidence_references=[],
                follow_up_questions=[],
            )
        )
        w = LLMWriter(provider, fallback_on_failure=True)
        result = w.final(
            brief=_make_brief(),
            verified_evidence=[_make_evidence("EVID-001")],
            verification=_make_verification(),
            critique=_make_critique(),
        )
        assert isinstance(result, FinalReport)
        # Fallback occurred — deterministic output does NOT contain the hallucinated ID
        assert "EVID-HALLUCINATED" not in result.markdown

    def test_hallucinated_in_partial_evidence_ids_triggers_fallback(self):
        """One finding references a valid ID, another references a fake ID → fallback."""
        provider = _FakeWriterProvider(
            LLMFinalReportSchema(
                executive_summary="S.",
                findings=[
                    LLMFindingSchema(text="Good", evidence_ids=["EVID-001"], confidence="high"),
                    LLMFindingSchema(text="Bad", evidence_ids=["EVID-FAKE"], confidence="low"),
                ],
                limitations=[],
                evidence_references=[],
                follow_up_questions=[],
            )
        )
        w = LLMWriter(provider, fallback_on_failure=True)
        result = w.final(
            brief=_make_brief(),
            verified_evidence=[_make_evidence("EVID-001")],
            verification=_make_verification(),
            critique=_make_critique(),
        )
        # Fallback triggered by partially hallucinated evidence IDs
        assert "EVID-FAKE" not in result.markdown

    def test_raises_when_fallback_disabled(self):
        w = LLMWriter(_FailingWriterProvider("timeout"), fallback_on_failure=False)
        with pytest.raises(LLMProviderError):
            w.final(
                brief=_make_brief(),
                verified_evidence=[_make_evidence("EVID-001")],
                verification=_make_verification(),
                critique=_make_critique(),
            )


class TestLLMWriterTruncation:
    def test_truncates_evidence_above_max_items(self):
        """Evidence count > max_evidence_items → only top-N passed to LLM prompt."""
        provider = _FakeWriterProvider(
            LLMFinalReportSchema(
                executive_summary="Summary.",
                findings=[LLMFindingSchema(text="F", evidence_ids=["EVID-001"], confidence="high")],
                limitations=["Truncated."],
                evidence_references=["EVID-001: S1"],
                follow_up_questions=[],
            )
        )
        w = LLMWriter(provider, max_evidence_items=2)
        evidence = [_make_evidence(f"EVID-{i:03d}") for i in range(1, 6)]  # 5 items
        result = w.final(
            brief=_make_brief(),
            verified_evidence=evidence,
            verification=_make_verification(),
            critique=_make_critique(),
        )
        assert isinstance(result, FinalReport)

    def test_exact_max_does_not_truncate(self):
        provider = _FakeWriterProvider(
            LLMFinalReportSchema(
                executive_summary="S.",
                findings=[LLMFindingSchema(text="F", evidence_ids=["EVID-001"], confidence="high")],
                limitations=[],
                evidence_references=["EVID-001: S1"],
                follow_up_questions=[],
            )
        )
        w = LLMWriter(provider, max_evidence_items=3)
        evidence = [_make_evidence(f"EVID-{i:03d}") for i in range(1, 4)]  # exactly 3
        result = w.final(
            brief=_make_brief(),
            verified_evidence=evidence,
            verification=_make_verification(),
            critique=_make_critique(),
        )
        assert isinstance(result, FinalReport)

"""Tests for WriterProtocol — deterministic Writer conformance."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

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


def _make_brief() -> ResearchBrief:
    return ResearchBrief(
        run_id="test-run",
        objective="Test research.",
        scope_boundaries=["scope"],
        assumptions=["assumption"],
        open_clarifications=[],
        perspectives=["p1"],
        success_criteria=["sc1"],
        research_tasks=[
            ResearchTask(
                research_task_id="T1",
                run_id="test-run",
                perspective="p1",
                objective="obj",
                query="q",
            )
        ],
    )


def _make_source(source_id: str, title: str = "Test Source") -> SourceResult:
    return SourceResult(
        source_id=source_id,
        provider="fixture",
        title=title,
        source_type=SourceType.BLOG,
        retrieved_at=datetime.now(timezone.utc),
        snippet="snippet",
        provider_rank=1,
    )


def _make_evidence(
    evidence_id: str,
    run_id: str = "test-run",
    supported_claims: list[str] | None = None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        run_id=run_id,
        research_task_id="T1",
        perspective="p1",
        source=_make_source(f"S-{evidence_id}"),
        authority_score=0.8,
        relevance_score=0.9,
        summary=f"Summary of {evidence_id}",
        key_points=["key point"],
        supported_claims=supported_claims or [f"Claim from {evidence_id}"],
        limitations=[],
        status=EvidenceStatus.VERIFIED,
        verification_notes=["ok"],
    )


class TestWriterProtocolConformance:
    """Writer MUST satisfy WriterProtocol."""

    def test_writer_is_subclass_of_writer_protocol(self):
        assert issubclass(Writer, WriterProtocol)

    def test_writer_instance_is_writer_protocol(self):
        w = Writer()
        assert isinstance(w, WriterProtocol)

    def test_draft_returns_draft_report(self):
        w = Writer()
        brief = _make_brief()
        evidence = [_make_evidence("EVID-001")]
        result = w.draft(brief=brief, evidence=evidence)
        assert isinstance(result, DraftReport)
        assert result.outline_markdown
        assert result.draft_markdown
        assert len(result.claims) >= 1

    def test_draft_returns_empty_claims_for_empty_evidence(self):
        w = Writer()
        brief = _make_brief()
        result = w.draft(brief=brief, evidence=[])
        assert isinstance(result, DraftReport)
        assert result.claims == []

    def test_final_returns_final_report(self):
        w = Writer()
        brief = _make_brief()
        evidence = [_make_evidence("EVID-001")]
        verification = VerificationResult(
            run_id="test-run",
            checked_at=datetime.now(timezone.utc),
            claim_results=[
                Claim(
                    claim_id="CL-001",
                    run_id="test-run",
                    text="Claim from EVID-001",
                    section_id="findings",
                    evidence_ids=["EVID-001"],
                    support_status=ClaimSupportStatus.SUPPORTED,
                )
            ],
            unsupported_claim_count=0,
            critical_hallucination_count=0,
            citation_completeness=1.0,
        )
        critique = CritiqueResult(
            run_id="test-run",
            missing_perspectives=[],
            weak_sources=[],
            duplicate_sections=[],
            unsupported_claims=[],
            limitations_to_add=[],
            decision=CritiqueDecision.PASS,
            next_phase=NextPhase.COMPLETE,
        )
        result = w.final(
            brief=brief,
            verified_evidence=evidence,
            verification=verification,
            critique=critique,
        )
        assert isinstance(result, FinalReport)
        assert result.markdown
        assert result.report_json

    def test_final_report_contains_evidence_id(self):
        w = Writer()
        brief = _make_brief()
        evidence = [_make_evidence("EVID-001")]
        verification = VerificationResult(
            run_id="test-run",
            checked_at=datetime.now(timezone.utc),
            claim_results=[
                Claim(
                    claim_id="CL-001",
                    run_id="test-run",
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
        critique = CritiqueResult(
            run_id="test-run",
            missing_perspectives=[],
            weak_sources=[],
            duplicate_sections=[],
            unsupported_claims=[],
            limitations_to_add=[],
            decision=CritiqueDecision.PASS,
            next_phase=NextPhase.COMPLETE,
        )
        result = w.final(
            brief=brief,
            verified_evidence=evidence,
            verification=verification,
            critique=critique,
        )
        assert "EVID-001" in result.markdown

    def test_writer_protocol_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            WriterProtocol()  # type: ignore[abstract]


class TestWriterAlias:
    """DeterministicWriter alias MUST be importable and identical to Writer."""

    def test_deterministic_writer_alias_exists(self):
        from traceresearch.agents.writer import DeterministicWriter  # type: ignore[attr-defined]

        assert DeterministicWriter is Writer

    def test_deterministic_writer_instance_is_writer(self):
        from traceresearch.agents.writer import DeterministicWriter  # type: ignore[attr-defined]

        dw = DeterministicWriter()
        assert isinstance(dw, Writer)

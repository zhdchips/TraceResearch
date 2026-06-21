"""Tests for LLM output Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from traceresearch.llm.schemas import (
    LLMClaimJudgmentSchema,
    LLMFinalReportSchema,
    LLMFindingSchema,
    LLMVerificationResultSchema,
)


# ---------------------------------------------------------------------------
# LLMFindingSchema
# ---------------------------------------------------------------------------

class TestLLMFindingSchema:
    def test_valid_finding(self):
        f = LLMFindingSchema(text="FastAPI is fast.", evidence_ids=["EVID-001"], confidence="high")
        assert f.text == "FastAPI is fast."
        assert f.evidence_ids == ["EVID-001"]
        assert f.confidence == "high"

    def test_empty_text_raises(self):
        with pytest.raises(ValidationError):
            LLMFindingSchema(text="", evidence_ids=["EVID-001"], confidence="high")

    def test_empty_evidence_ids_raises(self):
        """A finding MUST have at least one evidence reference."""
        with pytest.raises(ValidationError):
            LLMFindingSchema(text="Something", evidence_ids=[], confidence="medium")

    def test_invalid_confidence_raises(self):
        with pytest.raises(ValidationError):
            LLMFindingSchema(text="Ok", evidence_ids=["EVID-001"], confidence="super-high")

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            LLMFindingSchema(
                text="Ok",
                evidence_ids=["EVID-001"],
                confidence="low",
                extra_field="should_fail",
            )

    def test_multiple_evidence_ids(self):
        f = LLMFindingSchema(
            text="Multiple sources confirm...",
            evidence_ids=["EVID-001", "EVID-002", "EVID-003"],
            confidence="high",
        )
        assert len(f.evidence_ids) == 3


# ---------------------------------------------------------------------------
# LLMFinalReportSchema
# ---------------------------------------------------------------------------

class TestLLMFinalReportSchema:
    def _valid_finding(self, **overrides) -> dict:
        return {
            "text": "Finding text",
            "evidence_ids": ["EVID-001"],
            "confidence": "high",
            **overrides,
        }

    def test_valid_report(self):
        r = LLMFinalReportSchema(
            executive_summary="Summary here.",
            findings=[self._valid_finding()],
            limitations=["Limited data."],
            evidence_references=["EVID-001: Source Title"],
            follow_up_questions=["What about X?"],
        )
        assert r.executive_summary == "Summary here."
        assert len(r.findings) == 1
        assert r.limitations == ["Limited data."]
        assert r.evidence_references == ["EVID-001: Source Title"]
        assert r.follow_up_questions == ["What about X?"]

    def test_empty_executive_summary_raises(self):
        with pytest.raises(ValidationError):
            LLMFinalReportSchema(
                executive_summary="",
                findings=[self._valid_finding()],
                limitations=[],
                evidence_references=[],
                follow_up_questions=[],
            )

    def test_empty_findings_ok(self):
        """Zero findings is valid — represents 'no verified findings'."""
        r = LLMFinalReportSchema(
            executive_summary="Nothing found.",
            findings=[],
            limitations=["No data available."],
            evidence_references=[],
            follow_up_questions=["Retry with broader scope?"],
        )
        assert r.findings == []

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            LLMFinalReportSchema(
                executive_summary="Ok",
                findings=[],
                limitations=[],
                evidence_references=[],
                follow_up_questions=[],
                made_up_field="no",
            )

    def test_report_with_multiple_findings(self):
        r = LLMFinalReportSchema(
            executive_summary="Multi-finding report.",
            findings=[
                self._valid_finding(text="A", evidence_ids=["EVID-001"]),
                self._valid_finding(text="B", evidence_ids=["EVID-002"], confidence="low"),
            ],
            limitations=["Limitation 1", "Limitation 2"],
            evidence_references=["EVID-001: A", "EVID-002: B"],
            follow_up_questions=["Q1", "Q2"],
        )
        assert len(r.findings) == 2
        assert len(r.limitations) == 2
        assert len(r.evidence_references) == 2
        assert len(r.follow_up_questions) == 2


# ---------------------------------------------------------------------------
# LLMClaimJudgmentSchema
# ---------------------------------------------------------------------------

class TestLLMClaimJudgmentSchema:
    def test_valid_supported(self):
        j = LLMClaimJudgmentSchema(
            claim_id="CL-001",
            support_status="supported",
            reasoning="Evidence fully backs claim.",
        )
        assert j.claim_id == "CL-001"
        assert j.support_status == "supported"
        assert j.reasoning == "Evidence fully backs claim."

    def test_valid_weakly_supported(self):
        j = LLMClaimJudgmentSchema(
            claim_id="CL-002",
            support_status="weakly_supported",
            reasoning="Evidence partially covers.",
        )
        assert j.support_status == "weakly_supported"

    def test_valid_unsupported(self):
        j = LLMClaimJudgmentSchema(
            claim_id="CL-003",
            support_status="unsupported",
            reasoning="Evidence contradicts claim.",
        )
        assert j.support_status == "unsupported"

    def test_valid_conflicting(self):
        j = LLMClaimJudgmentSchema(
            claim_id="CL-004",
            support_status="conflicting",
            reasoning="Sources disagree.",
        )
        assert j.support_status == "conflicting"

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            LLMClaimJudgmentSchema(
                claim_id="CL-005",
                support_status="maybe",
                reasoning="Not a real status.",
            )

    def test_empty_claim_id_raises(self):
        with pytest.raises(ValidationError):
            LLMClaimJudgmentSchema(
                claim_id="",
                support_status="supported",
                reasoning="Needs claim_id.",
            )

    def test_empty_reasoning_raises(self):
        with pytest.raises(ValidationError):
            LLMClaimJudgmentSchema(
                claim_id="CL-006",
                support_status="supported",
                reasoning="",
            )

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            LLMClaimJudgmentSchema(
                claim_id="CL-007",
                support_status="supported",
                reasoning="Ok.",
                hallucination_score=0.9,
            )


# ---------------------------------------------------------------------------
# LLMVerificationResultSchema
# ---------------------------------------------------------------------------

class TestLLMVerificationResultSchema:
    def _valid_judgment(self, **overrides) -> dict:
        return {
            "claim_id": "CL-001",
            "support_status": "supported",
            "reasoning": "Evidence matches.",
            **overrides,
        }

    def test_valid_result(self):
        r = LLMVerificationResultSchema(
            claim_results=[self._valid_judgment()],
            overall_notes=["All claims verified."],
        )
        assert len(r.claim_results) == 1
        assert r.claim_results[0].claim_id == "CL-001"
        assert r.overall_notes == ["All claims verified."]

    def test_empty_claim_results_ok(self):
        """Zero claims → valid for empty draft."""
        r = LLMVerificationResultSchema(claim_results=[], overall_notes=["No claims to verify."])
        assert r.claim_results == []

    def test_multiple_judgments(self):
        r = LLMVerificationResultSchema(
            claim_results=[
                self._valid_judgment(claim_id="CL-001", support_status="supported"),
                self._valid_judgment(claim_id="CL-002", support_status="unsupported",
                                     reasoning="No evidence found."),
                self._valid_judgment(claim_id="CL-003", support_status="weakly_supported",
                                     reasoning="Partial match."),
            ],
            overall_notes=["Mixed results."],
        )
        assert len(r.claim_results) == 3

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            LLMVerificationResultSchema(
                claim_results=[],
                overall_notes=[],
                unknown_field="nope",
            )

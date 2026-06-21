"""Tests for LLMVerifier — mock LLMProvider, no real LLM calls."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import BaseModel

from traceresearch.agents.llm_verifier import LLMVerifier
from traceresearch.agents.verifier import Verifier
from traceresearch.agents.verifier_protocol import VerifierProtocol
from traceresearch.agents.writer import DraftReport
from traceresearch.evidence.models import (
    Claim,
    ClaimSupportStatus,
    Evidence,
    EvidenceStatus,
    SourceResult,
    SourceType,
    VerificationResult,
)
from traceresearch.llm.provider import LLMProvider, LLMProviderError
from traceresearch.llm.schemas import (
    LLMClaimJudgmentSchema,
    LLMVerificationResultSchema,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class _FakeProvider(LLMProvider):
    """Returns a pre-built LLMVerificationResultSchema."""

    def __init__(self, result: LLMVerificationResultSchema) -> None:
        self._result = result
        self._calls: list[dict] = []

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
        self._calls.append({"prompt": prompt, "schema": response_schema})
        if response_schema is not LLMVerificationResultSchema:
            raise LLMProviderError("invalid_response", "fake", "fake-model", 0)
        return self._result


class _FailingProvider(LLMProvider):
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


def _make_source(source_id: str) -> SourceResult:
    return SourceResult(
        source_id=source_id,
        provider="fixture",
        title=f"Source {source_id}",
        source_type=SourceType.BLOG,
        retrieved_at=datetime.now(timezone.utc),
        snippet="snippet text",
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
        summary=f"Summary of {evidence_id}: This source strongly supports claim about {evidence_id}.",
        key_points=["key point"],
        supported_claims=[f"Claim about {evidence_id}"],
        limitations=[],
        status=EvidenceStatus.CANDIDATE,
    )


def _make_claim(claim_id: str, evidence_ids: list[str], text: str | None = None) -> Claim:
    return Claim(
        claim_id=claim_id,
        run_id="test-run",
        text=text or f"Claim {claim_id}",
        section_id="findings",
        evidence_ids=evidence_ids,
        support_status=ClaimSupportStatus.SUPPORTED,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLLMVerifierSuccess:
    def test_implements_verifier_protocol(self):
        provider = _FakeProvider(
            LLMVerificationResultSchema(
                claim_results=[
                    LLMClaimJudgmentSchema(
                        claim_id="CL-001",
                        support_status="supported",
                        reasoning="Evidence matches.",
                    )
                ],
                overall_notes=["ok"],
            )
        )
        v = LLMVerifier(provider)
        assert isinstance(v, VerifierProtocol)

    def test_marks_supported_claim(self):
        provider = _FakeProvider(
            LLMVerificationResultSchema(
                claim_results=[
                    LLMClaimJudgmentSchema(
                        claim_id="CL-001",
                        support_status="supported",
                        reasoning="Strong alignment.",
                    )
                ],
                overall_notes=["All good."],
            )
        )
        v = LLMVerifier(provider)
        draft = DraftReport(
            outline_markdown="# Outline",
            draft_markdown="# Draft",
            claims=[_make_claim("CL-001", ["EVID-001"])],
        )
        evidence = [_make_evidence("EVID-001")]
        result = v.verify(run_id="test-run", draft=draft, evidence=evidence)
        assert result.claim_results[0].support_status == ClaimSupportStatus.SUPPORTED
        assert result.claim_results[0].claim_id == "CL-001"

    def test_marks_weakly_supported_claim(self):
        provider = _FakeProvider(
            LLMVerificationResultSchema(
                claim_results=[
                    LLMClaimJudgmentSchema(
                        claim_id="CL-001",
                        support_status="weakly_supported",
                        reasoning="Partial coverage.",
                    )
                ],
                overall_notes=["Weak support detected."],
            )
        )
        v = LLMVerifier(provider)
        draft = DraftReport(
            outline_markdown="# Outline",
            draft_markdown="# Draft",
            claims=[_make_claim("CL-001", ["EVID-001"])],
        )
        evidence = [_make_evidence("EVID-001")]
        result = v.verify(run_id="test-run", draft=draft, evidence=evidence)
        assert result.claim_results[0].support_status == ClaimSupportStatus.WEAKLY_SUPPORTED

    def test_marks_unsupported_claim(self):
        provider = _FakeProvider(
            LLMVerificationResultSchema(
                claim_results=[
                    LLMClaimJudgmentSchema(
                        claim_id="CL-001",
                        support_status="unsupported",
                        reasoning="No evidence found.",
                    )
                ],
                overall_notes=["Claim not grounded."],
            )
        )
        v = LLMVerifier(provider)
        draft = DraftReport(
            outline_markdown="# Outline",
            draft_markdown="# Draft",
            claims=[_make_claim("CL-001", ["EVID-001"])],
        )
        evidence = [_make_evidence("EVID-001")]
        result = v.verify(run_id="test-run", draft=draft, evidence=evidence)
        assert result.claim_results[0].support_status == ClaimSupportStatus.UNSUPPORTED

    def test_marks_conflicting_claim(self):
        provider = _FakeProvider(
            LLMVerificationResultSchema(
                claim_results=[
                    LLMClaimJudgmentSchema(
                        claim_id="CL-001",
                        support_status="conflicting",
                        reasoning="Sources disagree.",
                    )
                ],
                overall_notes=["Conflict detected."],
            )
        )
        v = LLMVerifier(provider)
        draft = DraftReport(
            outline_markdown="# Outline",
            draft_markdown="# Draft",
            claims=[_make_claim("CL-001", ["EVID-001"])],
        )
        evidence = [_make_evidence("EVID-001")]
        result = v.verify(run_id="test-run", draft=draft, evidence=evidence)
        assert result.claim_results[0].support_status == ClaimSupportStatus.CONFLICTING

    def test_empty_claims_returns_empty_result(self):
        """Should return empty result without calling LLM."""
        provider = _FakeProvider(
            LLMVerificationResultSchema(claim_results=[], overall_notes=[])
        )
        v = LLMVerifier(provider)
        draft = DraftReport(
            outline_markdown="# Outline",
            draft_markdown="# Draft",
            claims=[],
        )
        evidence = [_make_evidence("EVID-001")]
        result = v.verify(run_id="test-run", draft=draft, evidence=evidence)
        assert result.claim_results == []
        assert result.unsupported_claim_count == 0


class TestLLMVerifierFallback:
    def test_falls_back_deterministic_on_invalid_json(self):
        """LLM returns non-parseable JSON → fallback deterministic Verifier."""

        class _BrokenProvider(LLMProvider):
            @property
            def provider_name(self) -> str:
                return "broken"
            @property
            def model(self) -> str:
                return "broken"
            def complete(self, prompt, response_schema, system_prompt=None):
                # Return a schema that will fail model_validate_json
                return response_schema.model_validate_json("not json {")

        v = LLMVerifier(_BrokenProvider(), fallback_on_failure=True)
        draft = DraftReport(
            outline_markdown="# O", draft_markdown="# D",
            claims=[_make_claim("CL-001", ["EVID-001"])],
        )
        evidence = [_make_evidence("EVID-001")]
        result = v.verify(run_id="test-run", draft=draft, evidence=evidence)
        # Deterministic fallback: supported since evidence_id exists
        assert result.claim_results[0].support_status == ClaimSupportStatus.SUPPORTED
        assert result.notes[0] == "Deterministic fixture verifier checked claim evidence IDs."

    def test_falls_back_on_llm_provider_error(self):
        v = LLMVerifier(_FailingProvider("timeout"), fallback_on_failure=True)
        draft = DraftReport(
            outline_markdown="# O", draft_markdown="# D",
            claims=[_make_claim("CL-001", ["EVID-001"])],
        )
        evidence = [_make_evidence("EVID-001")]
        result = v.verify(run_id="test-run", draft=draft, evidence=evidence)
        assert result.claim_results[0].support_status == ClaimSupportStatus.SUPPORTED

    def test_falls_back_on_claim_id_mismatch(self):
        """LLM returns claim_ids that don't match input → fallback."""
        provider = _FakeProvider(
            LLMVerificationResultSchema(
                claim_results=[
                    LLMClaimJudgmentSchema(
                        claim_id="CL-999",  # not in draft
                        support_status="supported",
                        reasoning="Fake.",
                    )
                ],
                overall_notes=[],
            )
        )
        v = LLMVerifier(provider, fallback_on_failure=True)
        draft = DraftReport(
            outline_markdown="# O", draft_markdown="# D",
            claims=[_make_claim("CL-001", ["EVID-001"])],
        )
        evidence = [_make_evidence("EVID-001")]
        result = v.verify(run_id="test-run", draft=draft, evidence=evidence)
        assert result.claim_results[0].claim_id == "CL-001"
        # Deterministic fallback matched the real claim
        assert result.claim_results[0].support_status == ClaimSupportStatus.SUPPORTED

    def test_falls_back_on_extra_claim_ids(self):
        """LLM returns more claim_ids than input → fallback."""
        provider = _FakeProvider(
            LLMVerificationResultSchema(
                claim_results=[
                    LLMClaimJudgmentSchema(
                        claim_id="CL-001", support_status="supported", reasoning="Ok.",
                    ),
                    LLMClaimJudgmentSchema(
                        claim_id="CL-EXTRA", support_status="supported", reasoning="Extra.",
                    ),
                ],
                overall_notes=[],
            )
        )
        v = LLMVerifier(provider, fallback_on_failure=True)
        draft = DraftReport(
            outline_markdown="# O", draft_markdown="# D",
            claims=[_make_claim("CL-001", ["EVID-001"])],
        )
        evidence = [_make_evidence("EVID-001")]
        result = v.verify(run_id="test-run", draft=draft, evidence=evidence)
        # Fallback occurred
        assert result.claim_results[0].claim_id == "CL-001"

    def test_raises_when_fallback_disabled(self):
        v = LLMVerifier(_FailingProvider("timeout"), fallback_on_failure=False)
        draft = DraftReport(
            outline_markdown="# O", draft_markdown="# D",
            claims=[_make_claim("CL-001", ["EVID-001"])],
        )
        evidence = [_make_evidence("EVID-001")]
        with pytest.raises(LLMProviderError):
            v.verify(run_id="test-run", draft=draft, evidence=evidence)

    def test_preserves_reasoning_in_notes(self):
        provider = _FakeProvider(
            LLMVerificationResultSchema(
                claim_results=[
                    LLMClaimJudgmentSchema(
                        claim_id="CL-001",
                        support_status="supported",
                        reasoning="The evidence clearly states...",
                    )
                ],
                overall_notes=["Overall note."],
            )
        )
        v = LLMVerifier(provider)
        draft = DraftReport(
            outline_markdown="# O", draft_markdown="# D",
            claims=[_make_claim("CL-001", ["EVID-001"])],
        )
        evidence = [_make_evidence("EVID-001")]
        result = v.verify(run_id="test-run", draft=draft, evidence=evidence)
        assert "The evidence clearly states..." in result.claim_results[0].notes[0]
        assert "Overall note." in result.notes

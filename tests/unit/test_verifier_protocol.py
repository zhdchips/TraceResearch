"""Tests for VerifierProtocol — deterministic Verifier conformance."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

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


def _make_claim(
    claim_id: str,
    evidence_ids: list[str],
    run_id: str = "test-run",
    support_status: ClaimSupportStatus = ClaimSupportStatus.SUPPORTED,
    is_key: bool = True,
) -> Claim:
    return Claim(
        claim_id=claim_id,
        run_id=run_id,
        text=f"Claim {claim_id}",
        section_id="findings",
        evidence_ids=evidence_ids,
        support_status=support_status,
        is_key=is_key,
    )


def _make_source(source_id: str) -> SourceResult:
    return SourceResult(
        source_id=source_id,
        provider="fixture",
        title="Test Source",
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
        summary=f"Summary of {evidence_id}",
        key_points=["key point"],
        supported_claims=[f"Claim about {evidence_id}"],
        limitations=[],
        status=EvidenceStatus.CANDIDATE,
    )


class TestVerifierProtocolConformance:
    """Verifier MUST satisfy VerifierProtocol."""

    def test_verifier_is_subclass_of_verifier_protocol(self):
        assert issubclass(Verifier, VerifierProtocol)

    def test_verifier_instance_is_verifier_protocol(self):
        v = Verifier()
        assert isinstance(v, VerifierProtocol)

    def test_verify_returns_verification_result(self):
        v = Verifier()
        draft = DraftReport(
            outline_markdown="# Outline",
            draft_markdown="# Draft",
            claims=[_make_claim("CL-001", ["EVID-001"])],
        )
        evidence = [_make_evidence("EVID-001")]
        result = v.verify(run_id="test-run", draft=draft, evidence=evidence)
        assert isinstance(result, VerificationResult)
        assert result.run_id == "test-run"
        assert len(result.claim_results) == 1
        assert result.claim_results[0].claim_id == "CL-001"
        assert result.claim_results[0].support_status == ClaimSupportStatus.SUPPORTED

    def test_verify_marks_missing_evidence_as_unsupported(self):
        v = Verifier()
        draft = DraftReport(
            outline_markdown="# Outline",
            draft_markdown="# Draft",
            claims=[_make_claim("CL-001", ["EVID-999"])],
        )
        evidence = [_make_evidence("EVID-001")]  # CL-001 references EVID-999 (missing)
        result = v.verify(run_id="test-run", draft=draft, evidence=evidence)
        # Unsupport claim dropped; no claim_results since evidence_ids not matched
        assert result.unsupported_claim_count == 1

    def test_verify_empty_draft_returns_empty_results(self):
        v = Verifier()
        draft = DraftReport(
            outline_markdown="# Outline",
            draft_markdown="# Draft",
            claims=[],
        )
        evidence = [_make_evidence("EVID-001")]
        result = v.verify(run_id="test-run", draft=draft, evidence=evidence)
        assert result.claim_results == []

    def test_verify_returns_citation_completeness(self):
        v = Verifier()
        draft = DraftReport(
            outline_markdown="# Outline",
            draft_markdown="# Draft",
            claims=[
                _make_claim("CL-001", ["EVID-001"]),
                _make_claim("CL-002", ["EVID-002"]),
            ],
        )
        evidence = [_make_evidence("EVID-001"), _make_evidence("EVID-002")]
        result = v.verify(run_id="test-run", draft=draft, evidence=evidence)
        assert result.citation_completeness == 1.0

    def test_verifier_protocol_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            VerifierProtocol()  # type: ignore[abstract]


class TestVerifierAlias:
    """DeterministicVerifier alias MUST be importable and identical to Verifier."""

    def test_deterministic_verifier_alias_exists(self):
        from traceresearch.agents.verifier import DeterministicVerifier  # type: ignore[attr-defined]

        assert DeterministicVerifier is Verifier

    def test_deterministic_verifier_instance_is_verifier(self):
        from traceresearch.agents.verifier import DeterministicVerifier  # type: ignore[attr-defined]

        dv = DeterministicVerifier()
        assert isinstance(dv, Verifier)

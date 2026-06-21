"""Rule-based claim verifier for MVP fixture runs."""

from __future__ import annotations

from datetime import datetime, timezone

from traceresearch.agents.writer import DraftReport
from traceresearch.evidence.models import (
    Claim,
    ClaimSupportStatus,
    Evidence,
    VerificationResult,
)
from traceresearch.agents.verifier_protocol import VerifierProtocol


class Verifier(VerifierProtocol):
    def verify(self, *, run_id: str, draft: DraftReport, evidence: list[Evidence]) -> VerificationResult:
        evidence_ids = {item.evidence_id for item in evidence}
        claim_results: list[Claim] = []
        unsupported_count = 0

        for claim in draft.claims:
            supported_ids = [item for item in claim.evidence_ids if item in evidence_ids]
            if supported_ids:
                claim_results.append(
                    claim.model_copy(
                        update={
                            "evidence_ids": supported_ids,
                            "support_status": ClaimSupportStatus.SUPPORTED,
                            "notes": ["Supported by verified fixture evidence."],
                        }
                    )
                )
            else:
                unsupported_count += 1

        citation_completeness = 1.0 if claim_results else 0.0
        return VerificationResult(
            run_id=run_id,
            checked_at=datetime.now(timezone.utc),
            claim_results=claim_results,
            unsupported_claim_count=unsupported_count,
            critical_hallucination_count=0,
            citation_completeness=citation_completeness,
            notes=["Deterministic fixture verifier checked claim evidence IDs."],
        )


# Backward-compatible alias — deterministic Verifier is the canonical Verifier.
DeterministicVerifier = Verifier

"""LLM-backed Verifier — semantic claim-evidence alignment check."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from dataclasses import dataclass

from traceresearch.agents.verifier import Verifier
from traceresearch.agents.verifier_protocol import VerifierProtocol
from traceresearch.agents.writer import DraftReport
from traceresearch.evidence.models import (
    Claim,
    ClaimSupportStatus,
    Evidence,
    VerificationResult,
)
from traceresearch.llm.provider import LLMProvider, LLMProviderError
from traceresearch.llm.schemas import LLMVerificationResultSchema


@dataclass
class LLMVerifierConfig:
    """Configuration for LLM-backed Verifier."""

    fallback_on_failure: bool = True
    """When True, automatically fall back to deterministic Verifier on LLM error."""


class LLMVerifier(VerifierProtocol):
    """Verifier that uses an LLM to semantically judge claim-evidence alignment.

    Falls back to deterministic ``Verifier`` on provider error or schema
    mismatch unless ``fallback_on_failure`` is disabled.
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        fallback_on_failure: bool = True,
    ) -> None:
        self._provider = provider
        self._fallback_on_failure = fallback_on_failure
        self._deterministic = Verifier()

    # ------------------------------------------------------------------
    # VerifierProtocol
    # ------------------------------------------------------------------

    def verify(
        self, *, run_id: str, draft: DraftReport, evidence: list[Evidence]
    ) -> VerificationResult:
        # Short-circuit: nothing to verify
        if not draft.claims:
            return VerificationResult(
                run_id=run_id,
                checked_at=datetime.now(timezone.utc),
                claim_results=[],
                unsupported_claim_count=0,
                critical_hallucination_count=0,
                citation_completeness=0.0,
                notes=["No claims to verify."],
            )

        prompt = self._build_prompt(draft.claims, evidence)
        try:
            raw = self._provider.complete(prompt, LLMVerificationResultSchema)
        except (LLMProviderError, Exception):
            if self._fallback_on_failure:
                return self._deterministic.verify(
                    run_id=run_id, draft=draft, evidence=evidence
                )
            raise

        # Post-validate: claim IDs must match input exactly (set equality)
        input_ids = {c.claim_id for c in draft.claims}
        result_ids = {c.claim_id for c in raw.claim_results}
        if input_ids != result_ids:
            if self._fallback_on_failure:
                return self._deterministic.verify(
                    run_id=run_id, draft=draft, evidence=evidence
                )
            raise LLMProviderError(
                "schema_mismatch",
                self._provider.provider_name,
                self._provider.model,
                0,
            )

        # Map LLM schema → domain model
        support_map = {
            "supported": ClaimSupportStatus.SUPPORTED,
            "weakly_supported": ClaimSupportStatus.WEAKLY_SUPPORTED,
            "unsupported": ClaimSupportStatus.UNSUPPORTED,
            "conflicting": ClaimSupportStatus.CONFLICTING,
        }

        input_claims_by_id = {c.claim_id: c for c in draft.claims}
        claim_results: list[Claim] = []
        unsupported_count = 0
        for judgment in raw.claim_results:
            domain_status = support_map.get(
                judgment.support_status, ClaimSupportStatus.UNSUPPORTED
            )
            if domain_status == ClaimSupportStatus.UNSUPPORTED:
                unsupported_count += 1
            original = input_claims_by_id[judgment.claim_id]
            # key claims cannot be unsupported — downgrade is_key flag
            claim_is_key = (
                original.is_key
                if domain_status != ClaimSupportStatus.UNSUPPORTED
                else False
            )
            claim_results.append(
                Claim(
                    claim_id=judgment.claim_id,
                    run_id=run_id,
                    text=original.text,
                    section_id=original.section_id,
                    evidence_ids=original.evidence_ids,
                    support_status=domain_status,
                    notes=[judgment.reasoning],
                    is_key=claim_is_key,
                )
            )

        supported = sum(
            1 for c in claim_results if c.support_status == ClaimSupportStatus.SUPPORTED
        )
        total = len(claim_results)
        citation_completeness = supported / total if total > 0 else 0.0

        return VerificationResult(
            run_id=run_id,
            checked_at=datetime.now(timezone.utc),
            claim_results=claim_results,
            unsupported_claim_count=unsupported_count,
            critical_hallucination_count=0,
            citation_completeness=round(citation_completeness, 4),
            notes=list(raw.overall_notes),
        )

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_prompt(self, claims: list[Claim], evidence: list[Evidence]) -> str:
        evidence_lines = []
        for item in evidence:
            evidence_lines.append(
                f"EVIDENCE {item.evidence_id}: {item.summary}\n"
                f"  Key points: {', '.join(item.key_points)}\n"
                f"  Supported claims: {', '.join(item.supported_claims)}"
            )

        claim_lines = []
        for claim in claims:
            claim_lines.append(
                f"CLAIM {claim.claim_id}: {claim.text}\n"
                f"  References evidence: {', '.join(claim.evidence_ids)}"
            )

        return (
            "You are a research verifier. For each CLAIM below, judge whether the "
            "referenced EVIDENCE actually supports it.\n\n"
            "Return a JSON object with:\n"
            '  - claim_results: list of {claim_id, support_status, reasoning}\n'
            "    - support_status: one of supported, weakly_supported, unsupported, conflicting\n"
            '  - overall_notes: list of overall observations\n\n'
            "--- EVIDENCE ---\n"
            f"{chr(10).join(evidence_lines)}\n\n"
            "--- CLAIMS ---\n"
            f"{chr(10).join(claim_lines)}\n\n"
            "Judge each claim independently. Only mark as 'supported' if the evidence "
            "clearly substantiates the claim text."
        )

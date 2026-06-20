"""Rule-based post-verification critic."""

from __future__ import annotations

from traceresearch.evidence.models import (
    CritiqueDecision,
    CritiqueResult,
    Evidence,
    NextPhase,
    ResearchBrief,
    VerificationResult,
)


class Critic:
    def review(
        self,
        *,
        brief: ResearchBrief,
        evidence: list[Evidence],
        verification: VerificationResult,
    ) -> CritiqueResult:
        covered_perspectives = {item.perspective for item in evidence}
        missing_perspectives = [
            perspective
            for perspective in brief.perspectives
            if perspective not in covered_perspectives
        ]
        weak_sources = [
            item.evidence_id
            for item in evidence
            if item.authority_score < 0.6 or item.relevance_score < 0.6
        ]
        limitations_to_add = []
        if not evidence:
            limitations_to_add.append("No evidence was found for the requested research question.")

        has_blocker = bool(missing_perspectives or verification.unsupported_claim_count)
        return CritiqueResult(
            run_id=brief.run_id,
            missing_perspectives=missing_perspectives,
            weak_sources=weak_sources,
            duplicate_sections=[],
            unsupported_claims=[],
            limitations_to_add=limitations_to_add,
            decision=CritiqueDecision.REVISE if has_blocker else CritiqueDecision.PASS,
            next_phase=NextPhase.RESEARCH if has_blocker else NextPhase.COMPLETE,
        )

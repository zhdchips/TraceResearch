"""Outline-first deterministic report writer."""

from __future__ import annotations

from dataclasses import dataclass

from traceresearch.evidence.models import (
    Claim,
    ClaimSupportStatus,
    CritiqueResult,
    Evidence,
    ResearchBrief,
    VerificationResult,
)
from traceresearch.reports.renderer import render_evidence_references


@dataclass(frozen=True)
class DraftReport:
    outline_markdown: str
    draft_markdown: str
    claims: list[Claim]


@dataclass(frozen=True)
class FinalReport:
    markdown: str
    report_json: dict[str, object]


class Writer:
    def draft(self, *, brief: ResearchBrief, evidence: list[Evidence]) -> DraftReport:
        outline = self._outline(brief)
        claims: list[Claim] = []
        for index, item in enumerate(evidence, start=1):
            if not item.supported_claims:
                continue
            claims.append(
                Claim(
                    claim_id=f"CL-{brief.run_id}-{index:03d}",
                    run_id=brief.run_id,
                    text=item.supported_claims[0],
                    section_id="findings",
                    evidence_ids=[item.evidence_id],
                    support_status=ClaimSupportStatus.SUPPORTED,
                )
            )

        draft_lines = ["# Draft Report", "", "## Candidate Findings"]
        for claim in claims:
            draft_lines.append(f"- {claim.text} [{claim.evidence_ids[0]}]")

        return DraftReport(
            outline_markdown=outline,
            draft_markdown="\n".join(draft_lines) + "\n",
            claims=claims,
        )

    def final(
        self,
        *,
        brief: ResearchBrief,
        verified_evidence: list[Evidence],
        verification: VerificationResult,
        critique: CritiqueResult,
    ) -> FinalReport:
        claims = [
            claim
            for claim in verification.claim_results
            if claim.support_status == ClaimSupportStatus.SUPPORTED and claim.evidence_ids
        ]
        evidence_by_id = {item.evidence_id: item for item in verified_evidence}
        limitations = _unique(
            limitation
            for item in verified_evidence
            for limitation in item.limitations
        )
        if critique.limitations_to_add:
            limitations = _unique([*limitations, *critique.limitations_to_add])

        title = f"Research Report: {brief.objective}"
        findings = [
            f"- {claim.text} " + " ".join(f"[{evidence_id}]" for evidence_id in claim.evidence_ids)
            for claim in claims
        ]
        evidence_refs = render_evidence_references(verified_evidence).splitlines()
        follow_ups = [
            "- Validate these findings against live web sources in a later provider integration.",
            "- Add broader benchmark cases before making production recommendations.",
        ]

        markdown = "\n".join(
            [
                "# Title",
                title,
                "",
                "## Executive Summary",
                f"This report answers: {brief.objective}. Key findings are grounded in verified evidence IDs.",
                "",
                "## Research Scope",
                *[f"- {boundary}" for boundary in brief.scope_boundaries],
                "",
                "## Method Overview",
                "The Harness executed Planner, Researcher, Evidence Store, Writer draft claims, Verifier, Critic, and Writer final report in order.",
                "",
                "## Findings",
                *(findings or ["- No supported key findings were verified."]),
                "",
                "## Limitations",
                *(f"- {item}" for item in (limitations or ["Fixture-only evidence limits external validity."])),
                "",
                "## Evidence References",
                *(evidence_refs or ["- No verified evidence references."]),
                "",
                "## Follow-up Questions",
                *follow_ups,
                "",
            ]
        )

        report_json = {
            "run_id": brief.run_id,
            "title": title,
            "sections": [
                {
                    "section_id": "findings",
                    "heading": "Findings",
                    "content": "\n".join(findings),
                    "claims": [
                        {
                            "claim_id": claim.claim_id,
                            "text": claim.text,
                            "evidence_ids": claim.evidence_ids,
                            "support_status": claim.support_status.value,
                        }
                        for claim in claims
                    ],
                }
            ],
            "limitations": limitations,
            "unsupported_claims": [],
            "evidence_references": [
                f"{evidence_id}: {evidence_by_id[evidence_id].source.title}"
                for claim in claims
                for evidence_id in claim.evidence_ids
                if evidence_id in evidence_by_id
            ],
        }
        return FinalReport(markdown=markdown, report_json=report_json)

    def _outline(self, brief: ResearchBrief) -> str:
        return "\n".join(
            [
                "# Outline",
                "",
                "## Executive Summary",
                "## Research Scope",
                "## Method Overview",
                "## Findings",
                *[f"- {perspective}" for perspective in brief.perspectives],
                "## Limitations",
                "## Evidence References",
                "## Follow-up Questions",
                "",
            ]
        )


def _unique(items) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result

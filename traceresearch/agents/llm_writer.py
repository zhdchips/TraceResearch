"""LLM-backed Writer — generates natural final reports from verified evidence."""

from __future__ import annotations

from dataclasses import dataclass

from traceresearch.agents.writer import DraftReport, FinalReport, Writer
from traceresearch.agents.writer_protocol import WriterProtocol
from traceresearch.evidence.models import (
    CritiqueResult,
    Evidence,
    ResearchBrief,
    VerificationResult,
)
from traceresearch.llm.provider import LLMProvider, LLMProviderError
from traceresearch.llm.schemas import LLMFinalReportSchema


@dataclass
class LLMWriterConfig:
    """Configuration for LLM-backed Writer."""

    fallback_on_failure: bool = True
    """When True, automatically fall back to deterministic Writer on LLM error."""

    max_evidence_items: int = 10
    """Maximum number of evidence items to include in the LLM prompt."""


class LLMWriter(WriterProtocol):
    """Writer that uses an LLM to generate natural-language final reports.

    Falls back to deterministic ``Writer`` on provider error or schema
    mismatch unless ``fallback_on_failure`` is disabled.
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        fallback_on_failure: bool = True,
        max_evidence_items: int = 10,
    ) -> None:
        self._provider = provider
        self._fallback_on_failure = fallback_on_failure
        self._max_evidence_items = max_evidence_items
        self._deterministic = Writer()

    # ------------------------------------------------------------------
    # WriterProtocol
    # ------------------------------------------------------------------

    def draft(self, *, brief: ResearchBrief, evidence: list[Evidence]) -> DraftReport:
        """Delegate to deterministic Writer for draft generation."""
        return self._deterministic.draft(brief=brief, evidence=evidence)

    def final(
        self,
        *,
        brief: ResearchBrief,
        verified_evidence: list[Evidence],
        verification: VerificationResult,
        critique: CritiqueResult,
    ) -> FinalReport:
        # Truncate evidence if needed
        effective_evidence = verified_evidence
        if len(verified_evidence) > self._max_evidence_items:
            effective_evidence = verified_evidence[: self._max_evidence_items]

        # Collect valid evidence IDs for post-validation
        valid_evidence_ids = {item.evidence_id for item in verified_evidence}

        prompt = self._build_prompt(brief, effective_evidence, verification, critique)

        try:
            raw = self._provider.complete(prompt, LLMFinalReportSchema)
        except (LLMProviderError, Exception):
            if self._fallback_on_failure:
                return self._deterministic.final(
                    brief=brief,
                    verified_evidence=verified_evidence,
                    verification=verification,
                    critique=critique,
                )
            raise

        # Post-validate: every finding's evidence_ids MUST exist in the input set
        for finding in raw.findings:
            for evidence_id in finding.evidence_ids:
                if evidence_id not in valid_evidence_ids:
                    if self._fallback_on_failure:
                        return self._deterministic.final(
                            brief=brief,
                            verified_evidence=verified_evidence,
                            verification=verification,
                            critique=critique,
                        )
                    raise LLMProviderError(
                        "invalid_evidence_ref",
                        self._provider.provider_name,
                        self._provider.model,
                        0,
                    )

        # Build markdown from LLM output
        markdown = self._render_markdown(brief, raw)

        # Build report_json
        report_json = {
            "run_id": brief.run_id,
            "title": f"Research Report: {brief.objective}",
            "sections": [
                {
                    "section_id": "findings",
                    "heading": "Findings",
                    "content": "\n".join(
                        f"- {f.text} [{', '.join(f.evidence_ids)}]"
                        for f in raw.findings
                    ),
                    "claims": [
                        {
                            "claim_id": f"F-{i:03d}",
                            "text": f.text,
                            "evidence_ids": f.evidence_ids,
                            "support_status": "supported",
                        }
                        for i, f in enumerate(raw.findings, start=1)
                    ],
                }
            ],
            "limitations": raw.limitations,
            "unsupported_claims": [],
            "evidence_references": raw.evidence_references,
        }

        return FinalReport(markdown=markdown, report_json=report_json)

    # ------------------------------------------------------------------
    # Prompt & rendering
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        brief: ResearchBrief,
        evidence: list[Evidence],
        verification: VerificationResult,
        critique: CritiqueResult,
    ) -> str:
        evidence_lines = []
        for item in evidence:
            evidence_lines.append(
                f"EVIDENCE {item.evidence_id}:\n"
                f"  Title: {item.source.title}\n"
                f"  Summary: {item.summary}\n"
                f"  Key points: {'; '.join(item.key_points)}\n"
                f"  Supported claims: {'; '.join(item.supported_claims)}\n"
                f"  Limitations: {'; '.join(item.limitations) if item.limitations else 'none'}"
            )

        return (
            "You are a research report writer. Generate a structured final report "
            "based ONLY on the verified evidence provided below.\n\n"
            "Return a JSON object with:\n"
            '  - executive_summary: concise overview\n'
            '  - findings: list of {text, evidence_ids, confidence}\n'
            "    - confidence: one of high, medium, low\n"
            '  - limitations: list of known limitations\n'
            '  - evidence_references: list of "EVID-xxx: Source Title"\n'
            '  - follow_up_questions: list of questions for further research\n\n'
            "CRITICAL RULES:\n"
            "- Every finding MUST reference evidence_ids from the EXACT evidence IDs provided below.\n"
            "- Do NOT invent claims not supported by the evidence.\n"
            "- If no evidence supports a finding, state that.\n\n"
            f"Research objective: {brief.objective}\n\n"
            "--- VERIFIED EVIDENCE ---\n"
            f"{'\n'.join(evidence_lines)}\n\n"
            "--- GENERATE REPORT ---"
        )

    def _render_markdown(
        self, brief: ResearchBrief, raw: LLMFinalReportSchema
    ) -> str:
        findings_lines = []
        for finding in raw.findings:
            refs = " ".join(f"[{eid}]" for eid in finding.evidence_ids)
            findings_lines.append(f"- {finding.text} {refs} (confidence: {finding.confidence})")

        limitations_lines = [f"- {lim}" for lim in raw.limitations] if raw.limitations else ["- None identified."]
        refs_lines = [f"- {ref}" for ref in raw.evidence_references] if raw.evidence_references else ["- None."]
        questions_lines = [f"- {q}" for q in raw.follow_up_questions] if raw.follow_up_questions else ["- None."]

        return "\n".join(
            [
                f"# Research Report: {brief.objective}",
                "",
                "## Executive Summary",
                raw.executive_summary,
                "",
                "## Research Scope",
                *[f"- {b}" for b in brief.scope_boundaries],
                "",
                "## Method Overview",
                "LLM-backed Writer generated this report from verified evidence.",
                "",
                "## Findings",
                *(findings_lines or ["- No verified findings."]),
                "",
                "## Limitations",
                *limitations_lines,
                "",
                "## Evidence References",
                *refs_lines,
                "",
                "## Follow-up Questions",
                *questions_lines,
                "",
            ]
        )

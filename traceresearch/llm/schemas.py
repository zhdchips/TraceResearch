"""Pydantic schemas for LLM output validation.

These schemas act as the contract between LLM responses and the
TraceResearch domain layer. Every LLM call's output is validated
against one of these schemas before entering the system.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _StrictSchema(BaseModel):
    """Schema that rejects unknown fields — defense against LLM hallucination."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Writer output schemas
# ---------------------------------------------------------------------------


class LLMFindingSchema(_StrictSchema):
    """A single finding produced by the LLM Writer.

    Each finding MUST reference at least one evidence_id from the
    evidence set provided in the prompt.
    """

    text: str = Field(min_length=1, description="Finding text in natural language.")
    evidence_ids: list[str] = Field(
        min_length=1,
        description="Evidence IDs from the input set that support this finding.",
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="Writer's confidence in this finding."
    )


class LLMFinalReportSchema(_StrictSchema):
    """The structured final report produced by the LLM Writer."""

    executive_summary: str = Field(
        min_length=1,
        description="Concise overview of the research findings.",
    )
    findings: list[LLMFindingSchema] = Field(
        description="Research findings. Empty list means no verified findings."
    )
    limitations: list[str] = Field(
        description="Known limitations of this research."
    )
    evidence_references: list[str] = Field(
        description='Evidence references in "EVID-xxx: Source Title" format.'
    )
    follow_up_questions: list[str] = Field(
        description="Questions for further investigation."
    )


# ---------------------------------------------------------------------------
# Verifier output schemas
# ---------------------------------------------------------------------------


class LLMClaimJudgmentSchema(_StrictSchema):
    """LLM Verifier's judgment on a single claim."""

    claim_id: str = Field(min_length=1, description="Must match input claim ID exactly.")
    support_status: Literal[
        "supported", "weakly_supported", "unsupported", "conflicting"
    ] = Field(description="How well the evidence supports this claim.")
    reasoning: str = Field(
        min_length=1,
        description="Explanation of the judgment.",
    )


class LLMVerificationResultSchema(_StrictSchema):
    """The structured verification result produced by the LLM Verifier."""

    claim_results: list[LLMClaimJudgmentSchema] = Field(
        description="Judgment for each claim. Empty if no claims to verify."
    )
    overall_notes: list[str] = Field(
        description="Overall observations about evidence quality."
    )

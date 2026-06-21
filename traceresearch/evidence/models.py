"""Domain models for TraceResearch evidence and evaluation artifacts."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class StrictModel(BaseModel):
    """Base model with explicit fields only."""

    model_config = ConfigDict(extra="forbid")


class ResearchRunStatus(StrEnum):
    CREATED = "created"
    NEEDS_CLARIFICATION = "needs_clarification"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchTaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    NO_EVIDENCE = "no_evidence"
    FAILED = "failed"


class SourceType(StrEnum):
    OFFICIAL_DOC = "official_doc"
    PAPER = "paper"
    REPO = "repo"
    BLOG = "blog"
    NEWS = "news"
    REPORT = "report"
    UNKNOWN = "unknown"


class EvidenceStatus(StrEnum):
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ClaimSupportStatus(StrEnum):
    SUPPORTED = "supported"
    WEAKLY_SUPPORTED = "weakly_supported"
    UNSUPPORTED = "unsupported"
    CONFLICTING = "conflicting"


class CritiqueDecision(StrEnum):
    PASS = "pass"
    REVISE = "revise"
    FAIL = "fail"


class NextPhase(StrEnum):
    PLAN = "plan"
    RESEARCH = "research"
    VERIFY = "verify"
    WRITE = "write"
    EVAL = "eval"
    COMPLETE = "complete"


class ResearchRun(StrictModel):
    run_id: str = Field(min_length=1)
    input_query: str = Field(min_length=1)
    status: ResearchRunStatus
    created_at: datetime
    completed_at: datetime | None = None
    artifact_dir: str = Field(min_length=1)
    final_report_path: str | None = None
    eval_result_path: str | None = None

    @model_validator(mode="after")
    def completed_runs_have_final_report(self) -> "ResearchRun":
        if self.status == ResearchRunStatus.COMPLETED and not self.final_report_path:
            raise ValueError("completed ResearchRun requires final_report_path")
        return self


class ResearchTask(StrictModel):
    research_task_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    perspective: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    query: str = Field(min_length=1)
    status: ResearchTaskStatus = ResearchTaskStatus.PENDING
    source_limit: int = Field(default=5, ge=1)
    no_evidence_reason: str | None = None

    @model_validator(mode="after")
    def no_evidence_status_has_reason(self) -> "ResearchTask":
        if self.status == ResearchTaskStatus.NO_EVIDENCE and not self.no_evidence_reason:
            raise ValueError("no_evidence status requires no_evidence_reason")
        return self


class ResearchBrief(StrictModel):
    run_id: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    scope_boundaries: list[str]
    assumptions: list[str]
    open_clarifications: list[str]
    perspectives: list[str]
    success_criteria: list[str]
    research_tasks: list[ResearchTask]

    @model_validator(mode="after")
    def non_clarification_brief_has_work(self) -> "ResearchBrief":
        if not self.open_clarifications:
            if not self.perspectives:
                raise ValueError("research_brief requires perspectives when not clarifying")
            if not self.research_tasks:
                raise ValueError("research_brief requires research_tasks when not clarifying")
        return self


class SourceResult(StrictModel):
    source_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: HttpUrl | None = None
    source_type: SourceType
    publisher: str | None = None
    published_at: date | None = None
    retrieved_at: datetime
    snippet: str = Field(min_length=1)
    provider_rank: int = Field(ge=1)


class SourceDocument(StrictModel):
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: HttpUrl | None = None
    content_excerpt: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    retrieved_at: datetime


class Evidence(StrictModel):
    evidence_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    research_task_id: str = Field(min_length=1)
    perspective: str = Field(min_length=1)
    source: SourceResult
    authority_score: float = Field(ge=0.0, le=1.0)
    relevance_score: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=1)
    key_points: list[str]
    supported_claims: list[str]
    limitations: list[str]
    status: EvidenceStatus = EvidenceStatus.CANDIDATE
    verification_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def verified_evidence_has_content(self) -> "Evidence":
        if (
            self.status == EvidenceStatus.VERIFIED
            and not self.supported_claims
            and not self.limitations
        ):
            raise ValueError("verified Evidence requires supported_claims or limitations")
        return self


class Claim(StrictModel):
    claim_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    support_status: ClaimSupportStatus
    notes: list[str] = Field(default_factory=list)
    is_key: bool = True

    @model_validator(mode="after")
    def validate_support(self) -> "Claim":
        if self.support_status == ClaimSupportStatus.SUPPORTED and not self.evidence_ids:
            raise ValueError("supported Claim requires evidence_ids")
        if self.is_key and self.support_status == ClaimSupportStatus.UNSUPPORTED:
            raise ValueError("Key claims cannot be unsupported")
        return self


class VerificationResult(StrictModel):
    run_id: str = Field(min_length=1)
    checked_at: datetime
    claim_results: list[Claim]
    unsupported_claim_count: int = Field(ge=0)
    critical_hallucination_count: int = Field(ge=0)
    citation_completeness: float = Field(ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)


class CritiqueResult(StrictModel):
    run_id: str = Field(min_length=1)
    missing_perspectives: list[str]
    weak_sources: list[str]
    duplicate_sections: list[str]
    unsupported_claims: list[str]
    limitations_to_add: list[str]
    decision: CritiqueDecision
    next_phase: NextPhase
    failed_task_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def failing_decisions_do_not_complete(self) -> "CritiqueResult":
        if self.decision != CritiqueDecision.PASS and self.next_phase == NextPhase.COMPLETE:
            raise ValueError("fail or revise decision requires next_phase other than complete")
        return self


class EvalCase(StrictModel):
    case_id: str = Field(min_length=1)
    theme: str = Field(min_length=1)
    input_query: str = Field(min_length=1)
    expected_perspectives: list[str] = Field(min_length=1)
    fixture_source_ids: list[str] = Field(min_length=1)
    required_metrics: list[str] = Field(min_length=1)
    pass_conditions: dict[str, Any]


class EvalResult(StrictModel):
    eval_run_id: str = Field(min_length=1)
    created_at: datetime
    case_results: list[dict[str, Any]]
    metrics_summary: dict[str, Any]
    case_pass_rate: float = Field(ge=0.0, le=1.0)
    bad_case_notes: list[str]
    suggested_next_phase: str = Field(min_length=1)

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from traceresearch.evidence.models import (
    Claim,
    ClaimSupportStatus,
    CritiqueDecision,
    CritiqueResult,
    Evidence,
    EvidenceStatus,
    EvalCase,
    EvalResult,
    ResearchBrief,
    ResearchRun,
    ResearchRunStatus,
    ResearchTask,
    ResearchTaskStatus,
    SourceDocument,
    SourceResult,
    SourceType,
    VerificationResult,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _source_result() -> SourceResult:
    return SourceResult(
        source_id="src-1",
        provider="fixture",
        title="Official Runtime Guide",
        url="https://example.test/runtime",
        source_type=SourceType.OFFICIAL_DOC,
        publisher="Example",
        published_at=None,
        retrieved_at=_now(),
        snippet="Runtime overview",
        provider_rank=1,
    )


def test_research_run_completed_requires_final_report_path() -> None:
    with pytest.raises(ValidationError, match="final_report_path"):
        ResearchRun(
            run_id="run-1",
            input_query="Compare agent frameworks",
            status=ResearchRunStatus.COMPLETED,
            created_at=_now(),
            completed_at=_now(),
            artifact_dir="runs/run-1",
        )


def test_research_brief_requires_tasks_when_not_clarifying() -> None:
    with pytest.raises(ValidationError, match="research_tasks"):
        ResearchBrief(
            run_id="run-1",
            objective="Compare agent frameworks",
            scope_boundaries=["MVP"],
            assumptions=[],
            open_clarifications=[],
            perspectives=["technical"],
            success_criteria=["evidence-backed comparison"],
            research_tasks=[],
        )


def test_source_result_validates_provider_rank() -> None:
    with pytest.raises(ValidationError):
        SourceResult(
            source_id="src-1",
            provider="fixture",
            title="Bad Rank",
            source_type=SourceType.UNKNOWN,
            retrieved_at=_now(),
            snippet="bad",
            provider_rank=0,
        )


def test_source_document_stores_excerpt_not_raw_dump() -> None:
    doc = SourceDocument(
        source_id="src-1",
        title="Fixture Source",
        content_excerpt="Short excerpt",
        metadata={"case_id": "001"},
        retrieved_at=_now(),
    )

    assert doc.content_excerpt == "Short excerpt"


def test_evidence_score_bounds_and_verified_content_rules() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            evidence_id="EV-run-1-001",
            run_id="run-1",
            research_task_id="task-1",
            perspective="technical",
            source=_source_result(),
            authority_score=1.5,
            relevance_score=0.8,
            summary="summary",
            key_points=[],
            supported_claims=["claim"],
            limitations=[],
            status=EvidenceStatus.CANDIDATE,
            verification_notes=[],
        )

    with pytest.raises(ValidationError, match="supported_claims"):
        Evidence(
            evidence_id="EV-run-1-002",
            run_id="run-1",
            research_task_id="task-1",
            perspective="technical",
            source=_source_result(),
            authority_score=0.8,
            relevance_score=0.8,
            summary="summary",
            key_points=[],
            supported_claims=[],
            limitations=[],
            status=EvidenceStatus.VERIFIED,
            verification_notes=[],
        )


def test_key_claim_cannot_be_unsupported_and_supported_needs_evidence() -> None:
    with pytest.raises(ValidationError, match="Key claims"):
        Claim(
            claim_id="CL-1",
            run_id="run-1",
            text="Unsupported key claim",
            section_id="findings",
            evidence_ids=[],
            support_status=ClaimSupportStatus.UNSUPPORTED,
            is_key=True,
        )

    with pytest.raises(ValidationError, match="evidence_ids"):
        Claim(
            claim_id="CL-2",
            run_id="run-1",
            text="Supported claim without evidence",
            section_id="findings",
            evidence_ids=[],
            support_status=ClaimSupportStatus.SUPPORTED,
        )


def test_verification_and_critique_results_validate_bounds() -> None:
    claim = Claim(
        claim_id="CL-1",
        run_id="run-1",
        text="Supported claim",
        section_id="findings",
        evidence_ids=["EV-run-1-001"],
        support_status=ClaimSupportStatus.SUPPORTED,
    )
    result = VerificationResult(
        run_id="run-1",
        checked_at=_now(),
        claim_results=[claim],
        unsupported_claim_count=0,
        critical_hallucination_count=0,
        citation_completeness=1.0,
        notes=[],
    )

    assert result.citation_completeness == 1.0

    with pytest.raises(ValidationError, match="next_phase"):
        CritiqueResult(
            run_id="run-1",
            missing_perspectives=[],
            weak_sources=[],
            duplicate_sections=[],
            unsupported_claims=[],
            limitations_to_add=[],
            decision=CritiqueDecision.FAIL,
            next_phase="complete",
        )


def test_eval_case_and_result_models() -> None:
    case = EvalCase(
        case_id="001-framework-comparison",
        theme="Framework comparison",
        input_query="Compare frameworks",
        expected_perspectives=["technical", "risk"],
        fixture_source_ids=["src-1"],
        required_metrics=["planner_coverage"],
        pass_conditions={"critical_hallucination_count": 0},
    )
    result = EvalResult(
        eval_run_id="eval-1",
        created_at=_now(),
        case_results=[{"case_id": case.case_id, "passed": True}],
        metrics_summary={"case_pass_rate": 1.0},
        case_pass_rate=1.0,
        bad_case_notes=[],
        suggested_next_phase="complete",
    )

    assert result.case_pass_rate == 1.0


def test_research_task_no_evidence_requires_reason() -> None:
    with pytest.raises(ValidationError, match="no_evidence_reason"):
        ResearchTask(
            research_task_id="task-1",
            run_id="run-1",
            perspective="technical",
            objective="Find sources",
            query="query",
            status=ResearchTaskStatus.NO_EVIDENCE,
            source_limit=3,
        )

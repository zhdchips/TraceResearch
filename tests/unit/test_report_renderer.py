from datetime import datetime, timezone

from traceresearch.evidence.models import Evidence, EvidenceStatus, SourceResult, SourceType
from traceresearch.reports.renderer import render_evidence_references


def test_render_evidence_references_includes_review_metadata() -> None:
    evidence = Evidence(
        evidence_id="EV-run-1-001",
        run_id="run-1",
        research_task_id="task-1",
        perspective="technical",
        source=SourceResult(
            source_id="src-1",
            provider="fixture",
            title="Official Source",
            source_type=SourceType.OFFICIAL_DOC,
            publisher="Publisher",
            retrieved_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
            snippet="Snippet",
            provider_rank=1,
        ),
        authority_score=0.9,
        relevance_score=0.9,
        summary="Summary",
        key_points=["Point"],
        supported_claims=["Claim"],
        limitations=["Limited to fixture evidence."],
        status=EvidenceStatus.VERIFIED,
        verification_notes=["Verified"],
    )

    rendered = render_evidence_references([evidence])

    assert "[EV-run-1-001]" in rendered
    assert "Official Source" in rendered
    assert "official_doc" in rendered
    assert "2026-06-18T00:00:00Z" in rendered
    assert "Limited to fixture evidence." in rendered

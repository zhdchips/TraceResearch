from datetime import datetime, timezone
from pathlib import Path

from traceresearch.evidence.models import Evidence, EvidenceStatus, SourceResult, SourceType
from traceresearch.evidence.store import EvidenceStore


def _source(
    source_id: str = "src-1",
    *,
    url: str | None = "https://example.test/a",
    title: str = "Example Source",
    publisher: str | None = "Example",
) -> SourceResult:
    return SourceResult(
        source_id=source_id,
        provider="fixture",
        title=title,
        url=url,
        source_type=SourceType.OFFICIAL_DOC,
        publisher=publisher,
        published_at=None,
        retrieved_at=datetime.now(timezone.utc),
        snippet="snippet",
        provider_rank=1,
    )


def _evidence(evidence_id: str = "EV-run-1-001", source: SourceResult | None = None) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        run_id="run-1",
        research_task_id="task-1",
        perspective="technical",
        source=source or _source(),
        authority_score=0.9,
        relevance_score=0.8,
        summary="summary",
        key_points=["point"],
        supported_claims=["claim"],
        limitations=[],
        status=EvidenceStatus.CANDIDATE,
        verification_notes=[],
    )


def test_evidence_store_writes_and_reads_jsonl(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path / "evidence.jsonl")
    evidence = _evidence()

    store.add(evidence)

    assert store.get("EV-run-1-001") == evidence
    assert store.list_all() == [evidence]


def test_evidence_store_dedupes_by_normalized_url(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path / "evidence.jsonl")
    first = _evidence("EV-run-1-001", _source(url="https://example.test/a"))
    duplicate = _evidence("EV-run-1-002", _source(source_id="src-2", url="https://example.test/a/"))

    assert store.add(first) == first
    assert store.add(duplicate) == first
    assert len(store.list_all()) == 1


def test_evidence_store_dedupes_fixture_title_without_url(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path / "evidence.jsonl")
    first = _evidence("EV-run-1-001", _source(url=None, title="Fixture A", publisher="Fixture"))
    duplicate = _evidence("EV-run-1-002", _source(source_id="src-2", url=None, title="Fixture A", publisher="Fixture"))

    assert store.add(first) == first
    assert store.add(duplicate) == first
    assert len(store.list_all()) == 1


def test_evidence_store_updates_status_and_notes(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path / "evidence.jsonl")
    store.add(_evidence())

    updated = store.update_status(
        "EV-run-1-001",
        EvidenceStatus.VERIFIED,
        ["claim supported"],
    )

    assert updated.status == EvidenceStatus.VERIFIED
    assert updated.verification_notes == ["claim supported"]
    assert store.get("EV-run-1-001").status == EvidenceStatus.VERIFIED


def test_missing_evidence_lookup_returns_none(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path / "evidence.jsonl")

    assert store.get("missing") is None

from datetime import datetime, timezone
from pathlib import Path

import pytest

from traceresearch.evidence.models import ResearchTask, ResearchTaskStatus
from traceresearch.source_discovery.base import SourceDiscoveryError, SourceRef
from traceresearch.source_discovery.fixture_provider import (
    FixtureCaseNotFoundError,
    FixtureSourceNotFoundError,
    FixtureSourceProvider,
)


CASES_DIR = Path("eval/cases")
SOURCES_DIR = Path("eval/fixtures/sources")


def _task(
    *,
    perspective: str = "orchestration model",
    query: str = "Compare LangGraph and AutoGen orchestration",
    run_id: str = "run-1",
) -> ResearchTask:
    return ResearchTask(
        research_task_id="task-1",
        run_id=run_id,
        perspective=perspective,
        objective="Find fixture sources",
        query=query,
        status=ResearchTaskStatus.PENDING,
        source_limit=5,
    )


def test_fixture_provider_search_and_fetch_framework_case() -> None:
    provider = FixtureSourceProvider(
        cases_dir=CASES_DIR,
        sources_dir=SOURCES_DIR,
        case_id="001-framework-comparison",
    )

    results = provider.search(_task(), limit=2)
    document = provider.fetch(SourceRef(source_id=results[0].source_id, url=results[0].url))

    assert [result.provider_rank for result in results] == [1, 2]
    assert results[0].provider == "fixture"
    assert document.source_id == results[0].source_id
    assert document.content_excerpt
    assert document.metadata["supported_claims"]


def test_fixture_provider_supports_all_seed_cases() -> None:
    provider = FixtureSourceProvider(cases_dir=CASES_DIR, sources_dir=SOURCES_DIR)

    for case_id, case in provider.load_eval_cases().items():
        case_provider = provider.for_case(case_id)
        task = _task(
            perspective=case.expected_perspectives[0],
            query=case.input_query,
            run_id=case_id,
        )

        results = case_provider.search(task, limit=10)

        assert results
        assert {result.source_id for result in results}.issubset(set(case.fixture_source_ids))


def test_search_filters_by_perspective_and_query_deterministically() -> None:
    provider = FixtureSourceProvider(
        cases_dir=CASES_DIR,
        sources_dir=SOURCES_DIR,
        case_id="004-openhands-runtime",
    )
    task = _task(
        perspective="traceability",
        query="event stream traceability actions observations",
    )

    first = provider.search(task, limit=3)
    second = provider.search(task, limit=3)

    assert [result.source_id for result in first] == [result.source_id for result in second]
    assert first[0].source_id == "004-architecture-note"


def test_fetch_exposes_authority_and_conflicting_evidence_metadata() -> None:
    provider = FixtureSourceProvider(
        cases_dir=CASES_DIR,
        sources_dir=SOURCES_DIR,
        case_id="005-rag-2026",
    )

    document = provider.fetch(SourceRef(source_id="005-long-context-challenge"))

    assert document.metadata["authority_score"] == 0.86
    assert document.metadata["authority_signal"] == "benchmark paper"
    assert document.metadata["conflicting_evidence"] is True
    assert document.metadata["supported_claims"]


def test_missing_source_id_raises_stable_provider_error() -> None:
    provider = FixtureSourceProvider(cases_dir=CASES_DIR, sources_dir=SOURCES_DIR)

    with pytest.raises(FixtureSourceNotFoundError) as exc_info:
        provider.fetch(SourceRef(source_id="missing-source"))

    assert isinstance(exc_info.value, SourceDiscoveryError)
    assert exc_info.value.code == "fixture_source_not_found"


def test_missing_case_id_raises_stable_provider_error() -> None:
    provider = FixtureSourceProvider(cases_dir=CASES_DIR, sources_dir=SOURCES_DIR)

    with pytest.raises(FixtureCaseNotFoundError) as exc_info:
        provider.search_for_case("missing-case", _task(), limit=3)

    assert exc_info.value.code == "fixture_case_not_found"


def test_empty_result_for_unmatched_perspective() -> None:
    provider = FixtureSourceProvider(
        cases_dir=CASES_DIR,
        sources_dir=SOURCES_DIR,
        case_id="001-framework-comparison",
    )

    results = provider.search(
        _task(perspective="unrelated biology", query="protein folding"),
        limit=5,
    )

    assert results == []


def test_provider_handles_case_with_no_source_file(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    sources_dir = tmp_path / "sources"
    cases_dir.mkdir()
    sources_dir.mkdir()
    (cases_dir / "empty.yml").write_text(
        "\n".join(
            [
                "case_id: empty-case",
                "theme: Empty fixture case",
                "input_query: Find missing sources",
                "expected_perspectives:",
                "  - missing",
                "fixture_source_ids:",
                "  - missing-source",
                "required_metrics:",
                "  - planner_coverage",
                "pass_conditions:",
                "  critical_hallucination_count: 0",
            ]
        ),
        encoding="utf-8",
    )
    provider = FixtureSourceProvider(cases_dir=cases_dir, sources_dir=sources_dir)

    assert provider.search_for_case("empty-case", _task(perspective="missing"), limit=5) == []


def test_fixture_source_dates_are_loaded_as_model_values() -> None:
    provider = FixtureSourceProvider(
        cases_dir=CASES_DIR,
        sources_dir=SOURCES_DIR,
        case_id="002-financial-grounding",
    )

    [result] = provider.search(
        _task(perspective="regulatory grounding", query="SEC investor risk"),
        limit=1,
    )

    assert result.retrieved_at <= datetime.now(timezone.utc)

from pathlib import Path

from traceresearch.source_discovery.fixture_provider import FixtureSourceProvider


CASES_DIR = Path("eval/cases")
SOURCES_DIR = Path("eval/fixtures/sources")


def test_loads_all_seed_eval_cases() -> None:
    provider = FixtureSourceProvider(cases_dir=CASES_DIR, sources_dir=SOURCES_DIR)

    cases = provider.load_eval_cases()

    assert list(cases) == [
        "001-framework-comparison",
        "002-financial-grounding",
        "003-ai-coding-agent-trends",
        "004-openhands-runtime",
        "005-rag-2026",
    ]
    assert all(case.fixture_source_ids for case in cases.values())


def test_eval_cases_define_required_metrics_and_pass_conditions() -> None:
    provider = FixtureSourceProvider(cases_dir=CASES_DIR, sources_dir=SOURCES_DIR)
    required = {
        "planner_coverage",
        "source_relevance",
        "citation_completeness",
        "faithfulness",
        "critical_hallucination_count",
    }

    for case in provider.load_eval_cases().values():
        assert required.issubset(set(case.required_metrics))
        assert case.pass_conditions["critical_hallucination_count"] == 0
        assert case.expected_perspectives


def test_each_eval_case_references_existing_fixture_sources() -> None:
    provider = FixtureSourceProvider(cases_dir=CASES_DIR, sources_dir=SOURCES_DIR)
    source_ids = set(provider.load_fixture_sources())

    for case in provider.load_eval_cases().values():
        assert set(case.fixture_source_ids).issubset(source_ids)

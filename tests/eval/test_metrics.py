import json
from pathlib import Path

from traceresearch.eval.metrics import (
    REQUIRED_METRIC_NAMES,
    calculate_case_metrics,
    summarize_case_results,
)
from traceresearch.harness.orchestrator import ResearchHarness
from traceresearch.source_discovery.fixture_provider import FixtureSourceProvider


def test_metrics_calculator_reports_required_numeric_and_pass_fail(tmp_path: Path) -> None:
    case = FixtureSourceProvider().load_eval_case("001-framework-comparison")
    run = ResearchHarness().run_fixture(
        query=case.input_query,
        case_id=case.case_id,
        output_dir=tmp_path / "runs",
    )

    result = calculate_case_metrics(run.artifact_dir, case)

    assert set(REQUIRED_METRIC_NAMES).issubset(result["metrics"])
    assert set(REQUIRED_METRIC_NAMES).issubset(result["pass_fail"])
    assert result["metrics"]["planner_coverage"] == 1.0
    assert result["metrics"]["perspective_diversity"] == 1.0
    assert result["metrics"]["source_relevance"] >= 0.7
    assert result["metrics"]["source_authority"] >= 0.7
    assert result["metrics"]["citation_completeness"] == 1.0
    assert result["metrics"]["faithfulness"] == 1.0
    assert result["metrics"]["unsupported_claim_count"] == 0
    assert result["metrics"]["critical_hallucination_count"] == 0
    assert result["passed"] is True


def test_metrics_flags_missing_evidence(tmp_path: Path) -> None:
    case = FixtureSourceProvider().load_eval_case("001-framework-comparison")
    run = ResearchHarness().run_fixture(
        query=case.input_query,
        case_id=case.case_id,
        output_dir=tmp_path / "runs",
    )
    (run.artifact_dir / "evidence.jsonl").write_text("", encoding="utf-8")

    result = calculate_case_metrics(run.artifact_dir, case)

    assert result["metrics"]["source_relevance"] == 0.0
    assert result["metrics"]["source_authority"] == 0.0
    assert result["metrics"]["faithfulness"] == 0.0
    assert result["pass_fail"]["faithfulness"] is False
    assert result["passed"] is False
    assert any("missing verified evidence" in note for note in result["bad_case_notes"])


def test_metrics_flags_unsupported_claims(tmp_path: Path) -> None:
    case = FixtureSourceProvider().load_eval_case("001-framework-comparison")
    run = ResearchHarness().run_fixture(
        query=case.input_query,
        case_id=case.case_id,
        output_dir=tmp_path / "runs",
    )
    report_path = run.artifact_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["unsupported_claims"] = ["This unsupported finding should fail eval."]
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = calculate_case_metrics(run.artifact_dir, case)

    assert result["metrics"]["unsupported_claim_count"] == 1
    assert result["pass_fail"]["unsupported_claim_count"] is False
    assert result["metrics"]["critical_hallucination_count"] == 1
    assert result["passed"] is False
    assert any("unsupported claims" in note for note in result["bad_case_notes"])


def test_case_pass_rate_summary() -> None:
    summary = summarize_case_results(
        [
            {"case_id": "pass", "passed": True, "metrics": {"planner_coverage": 1.0}},
            {"case_id": "fail", "passed": False, "metrics": {"planner_coverage": 0.0}},
        ]
    )

    assert summary["case_pass_rate"] == 0.5
    assert summary["passed_cases"] == 1
    assert summary["failed_cases"] == 1
    assert summary["metric_averages"]["planner_coverage"] == 0.5

import json
from pathlib import Path

from typer.testing import CliRunner

from traceresearch.cli import app
from traceresearch.eval.runner import EvalRunner


def test_eval_runner_executes_all_seed_cases_and_writes_summary(tmp_path: Path) -> None:
    results_dir = tmp_path / "eval" / "results"
    runner = EvalRunner(
        cases_dir=Path("eval/cases"),
        results_dir=results_dir,
        runs_dir=tmp_path / "runs",
    )

    result = runner.run(source_provider="fixture")

    assert len(result.case_results) == 5
    assert result.result_path.parent == results_dir
    assert result.result_path.exists()

    payload = json.loads(result.result_path.read_text(encoding="utf-8"))
    assert payload["case_pass_rate"] == 1.0
    assert payload["metrics_summary"]["case_pass_rate"] == 1.0
    assert payload["bad_case_notes"] == []
    assert payload["suggested_next_phase"] == "complete"
    assert {item["case_id"] for item in payload["case_results"]} == {
        "001-framework-comparison",
        "002-financial-grounding",
        "003-ai-coding-agent-trends",
        "004-openhands-runtime",
        "005-rag-2026",
    }


def test_eval_runner_records_failed_case_notes(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    original_case = Path("eval/cases/001-framework-comparison.yml")
    case_text = original_case.read_text(encoding="utf-8").replace(
        "  - orchestration model",
        "  - missing regulatory audit perspective",
    )
    (cases_dir / original_case.name).write_text(case_text, encoding="utf-8")

    runner = EvalRunner(
        cases_dir=cases_dir,
        results_dir=tmp_path / "eval" / "results",
        runs_dir=tmp_path / "runs",
    )

    result = runner.run(source_provider="fixture")

    assert result.case_pass_rate == 0.0
    assert result.bad_case_notes
    assert result.suggested_next_phase == "eval"
    payload = json.loads(result.result_path.read_text(encoding="utf-8"))
    assert payload["bad_case_notes"] == result.bad_case_notes
    assert "001-framework-comparison" in payload["bad_case_notes"][0]


def test_cli_eval_command_outputs_summary_and_result_file(tmp_path: Path) -> None:
    results_dir = tmp_path / "eval" / "results"
    runs_dir = tmp_path / "runs"

    cli_result = CliRunner().invoke(
        app,
        [
            "eval",
            "--cases-dir",
            "eval/cases",
            "--source-provider",
            "fixture",
            "--results-dir",
            str(results_dir),
            "--runs-dir",
            str(runs_dir),
        ],
    )

    assert cli_result.exit_code == 0, cli_result.output
    assert "case_pass_rate=1.00" in cli_result.output
    assert "failed_case_ids=none" in cli_result.output
    result_file_line = next(
        line for line in cli_result.output.splitlines() if line.startswith("result_file=")
    )
    result_file = Path(result_file_line.split("=", 1)[1])
    assert result_file.exists()


def test_eval_plan_artifact_has_required_headings_and_skill_reference() -> None:
    text = Path("specs/001-deep-research-multi-agent-mvp/eval.md").read_text(
        encoding="utf-8"
    )

    assert "$speckit-ai-eval-review-eval" in text
    for heading in [
        "# Eval Plan",
        "## Scope",
        "## Metrics",
        "## Cases",
        "## Commands",
        "## Latest Result",
        "## Bad Cases",
        "## Next Review Focus",
    ]:
        assert heading in text

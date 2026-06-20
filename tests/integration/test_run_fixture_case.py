import json
from pathlib import Path

from typer.testing import CliRunner

from traceresearch.cli import app


REQUIRED_COMPLETED_RUN_ARTIFACTS = {
    "research_brief.json",
    "research_tasks.json",
    "evidence.jsonl",
    "verification.json",
    "critique.json",
    "outline.md",
    "draft_report.md",
    "final_report.md",
    "report.json",
    "trace.jsonl",
}


def _run_framework_fixture_case(tmp_path: Path) -> tuple[Path, str]:
    output_dir = tmp_path / "runs"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "run",
            "--query",
            "Compare LangGraph, AutoGen, and CrewAI for building research agents",
            "--source-provider",
            "fixture",
            "--case-id",
            "001-framework-comparison",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "run_id" in result.output
    assert "status" in result.output

    run_dirs = [path for path in output_dir.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    return run_dirs[0], result.output


def test_fixture_run_generates_required_artifacts(tmp_path: Path) -> None:
    artifact_dir, _output = _run_framework_fixture_case(tmp_path)

    produced_files = {path.name for path in artifact_dir.iterdir() if path.is_file()}

    assert REQUIRED_COMPLETED_RUN_ARTIFACTS.issubset(produced_files)
    assert (artifact_dir / "final_report.md").is_file()
    assert (artifact_dir / "report.json").is_file()


def test_fixture_run_report_artifacts_follow_contract(tmp_path: Path) -> None:
    artifact_dir, _output = _run_framework_fixture_case(tmp_path)

    final_report = (artifact_dir / "final_report.md").read_text(encoding="utf-8")
    report = json.loads((artifact_dir / "report.json").read_text(encoding="utf-8"))

    for heading in [
        "Title",
        "Executive Summary",
        "Research Scope",
        "Method Overview",
        "Findings",
        "Limitations",
        "Evidence References",
        "Follow-up Questions",
    ]:
        assert heading in final_report

    assert report["run_id"]
    assert report["title"]
    assert report["sections"]
    assert report["evidence_references"]
    assert report["unsupported_claims"] == []

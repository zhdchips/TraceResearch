import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from traceresearch.cli import app


def _run_fixture_case(tmp_path: Path) -> Path:
    output_dir = tmp_path / "runs"
    result = CliRunner().invoke(
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
    assert "status=completed" in result.output
    assert "provider_not_configured" not in result.output
    run_dirs = [path for path in output_dir.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    return run_dirs[0]


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _assert_fixture_artifacts(run_dir: Path) -> None:
    evidence_rows = _jsonl(run_dir / "evidence.jsonl")
    trace_rows = _jsonl(run_dir / "trace.jsonl")
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))

    assert evidence_rows
    for row in evidence_rows:
        source = row["source"]
        assert source["provider"] == "fixture"
        assert not str(source["source_id"]).startswith("exa:")
        assert not str(source["source_id"]).startswith("web:")

    tool_names = {row.get("tool_name") for row in trace_rows if row.get("tool_name")}
    assert "fixture.search" in tool_names
    assert "exa.search" not in tool_names
    assert "web_search" not in tool_names
    assert report["unsupported_claims"] == []


def test_fixture_run_without_exa_key_still_uses_fixture_provider(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRACERESEARCH_WEB_PROVIDER", "exa")
    monkeypatch.delenv("EXA_API_KEY", raising=False)

    run_dir = _run_fixture_case(tmp_path)

    _assert_fixture_artifacts(run_dir)


def test_fixture_run_with_exa_key_still_uses_fixture_provider(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRACERESEARCH_WEB_PROVIDER", "exa")
    monkeypatch.setenv("EXA_API_KEY", "test-exa-secret")
    monkeypatch.setenv("TRACERESEARCH_WEB_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("TRACERESEARCH_WEB_MAX_RESULTS", "1")

    run_dir = _run_fixture_case(tmp_path)

    _assert_fixture_artifacts(run_dir)
    artifact_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in run_dir.iterdir()
        if path.is_file()
    )
    assert "test-exa-secret" not in artifact_text


def test_fixture_case_id_path_is_independent_from_web_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRACERESEARCH_WEB_PROVIDER", "unsupported-live-provider")
    monkeypatch.setenv("EXA_API_KEY", "test-exa-secret")

    run_dir = _run_fixture_case(tmp_path)
    brief = json.loads((run_dir / "research_brief.json").read_text(encoding="utf-8"))
    evidence_rows = _jsonl(run_dir / "evidence.jsonl")

    assert run_dir.name.startswith("001-framework-comparison-")
    assert brief["run_id"].startswith("001-framework-comparison-")
    case = yaml.safe_load(
        Path("eval/cases/001-framework-comparison.yml").read_text(encoding="utf-8")
    )
    assert {
        row["source"]["source_id"] for row in evidence_rows
    } <= set(case["fixture_source_ids"])


def test_fixture_eval_ignores_live_provider_environment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRACERESEARCH_WEB_PROVIDER", "unsupported-live-provider")
    monkeypatch.setenv("EXA_API_KEY", "test-exa-secret")

    result = CliRunner().invoke(
        app,
        [
            "eval",
            "--cases-dir",
            "eval/cases",
            "--source-provider",
            "fixture",
            "--results-dir",
            str(tmp_path / "eval" / "results"),
            "--runs-dir",
            str(tmp_path / "runs"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "case_pass_rate=1.00" in result.output
    assert "failed_case_ids=none" in result.output

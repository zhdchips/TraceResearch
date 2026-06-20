import json
from pathlib import Path

from typer.testing import CliRunner

from traceresearch.cli import app


AMBIGUOUS_CASES = [
    ("missing research object", "Compare the best options for adoption."),
    ("missing time range", "Analyze current AI coding agent market trends."),
    ("missing output goal", "Research LangGraph, AutoGen, and CrewAI."),
    ("over-broad query", "Research everything about artificial intelligence."),
]


def _run_query(tmp_path: Path, query: str) -> Path:
    output_dir = tmp_path / "runs"
    result = CliRunner().invoke(
        app,
        [
            "run",
            "--query",
            query,
            "--source-provider",
            "fixture",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "status=needs_clarification" in result.output
    run_dirs = [path for path in output_dir.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    return run_dirs[0]


def test_ambiguous_queries_write_brief_and_trace_only(tmp_path: Path) -> None:
    for label, query in AMBIGUOUS_CASES:
        artifact_dir = _run_query(tmp_path / label.replace(" ", "-"), query)

        assert (artifact_dir / "research_brief.json").is_file()
        assert (artifact_dir / "trace.jsonl").is_file()
        assert not (artifact_dir / "research_tasks.json").exists()
        assert not (artifact_dir / "evidence.jsonl").exists()
        assert not (artifact_dir / "final_report.md").exists()
        assert not (artifact_dir / "report.json").exists()

        brief = json.loads((artifact_dir / "research_brief.json").read_text(encoding="utf-8"))
        assert brief["open_clarifications"] or brief["assumptions"]
        assert brief["research_tasks"] == []


def test_ambiguous_queries_do_not_invoke_downstream_agents(tmp_path: Path) -> None:
    artifact_dir = _run_query(tmp_path, "Research everything about technology.")

    trace_events = [
        json.loads(line)
        for line in (artifact_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    roles = {event["agent_role"] for event in trace_events}
    statuses = {event["status"] for event in trace_events}

    assert "Planner" in roles
    assert "Harness" in roles
    assert roles.isdisjoint({"Researcher", "Writer", "Verifier", "Critic"})
    assert "needs_clarification" in statuses

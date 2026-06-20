import re
from pathlib import Path

from typer.testing import CliRunner

from traceresearch.cli import app
from traceresearch.evidence.models import ResearchRunStatus
from traceresearch.harness.run_state import RunState
from traceresearch.trace.models import AgentRole


def _run_framework_fixture_case(tmp_path: Path) -> Path:
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
    run_dirs = [path for path in output_dir.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    return run_dirs[0]


def test_report_evidence_id_traces_to_evidence_and_agent_step(tmp_path: Path) -> None:
    run_dir = _run_framework_fixture_case(tmp_path)
    state = RunState(run_dir)
    report_text = state.report_paths().final_report.read_text(encoding="utf-8")

    match = re.search(r"\[(EV-[^\]]+)\]", report_text)

    assert match is not None
    evidence = state.evidence_by_id(match.group(1))
    assert evidence is not None
    assert evidence.status == "verified"

    trace_events = state.trace_events()
    assert any(event.agent_role == AgentRole.RESEARCHER for event in trace_events)
    assert any(event.task_id == evidence.research_task_id for event in trace_events)
    assert state.status() == ResearchRunStatus.COMPLETED

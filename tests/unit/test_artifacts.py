from pathlib import Path

import pytest

from traceresearch.harness.artifacts import RunArtifacts


def test_create_run_directory_and_required_paths(tmp_path: Path) -> None:
    artifacts = RunArtifacts.create(base_dir=tmp_path, run_id="run-1")

    assert artifacts.run_dir == tmp_path / "run-1"
    assert artifacts.run_dir.is_dir()
    assert artifacts.research_brief.name == "research_brief.json"
    assert artifacts.research_tasks.name == "research_tasks.json"
    assert artifacts.evidence.name == "evidence.jsonl"
    assert artifacts.verification.name == "verification.json"
    assert artifacts.critique.name == "critique.json"
    assert artifacts.outline.name == "outline.md"
    assert artifacts.draft_report.name == "draft_report.md"
    assert artifacts.final_report.name == "final_report.md"
    assert artifacts.report_json.name == "report.json"
    assert artifacts.trace.name == "trace.jsonl"


def test_create_is_idempotent(tmp_path: Path) -> None:
    first = RunArtifacts.create(base_dir=tmp_path, run_id="run-1")
    second = RunArtifacts.create(base_dir=tmp_path, run_id="run-1")

    assert first == second


@pytest.mark.parametrize("bad_run_id", ["../escape", "nested/run", "", "."])
def test_run_id_rejects_path_traversal(tmp_path: Path, bad_run_id: str) -> None:
    with pytest.raises(ValueError):
        RunArtifacts.create(base_dir=tmp_path, run_id=bad_run_id)


def test_as_dict_contains_all_required_files(tmp_path: Path) -> None:
    artifacts = RunArtifacts.create(base_dir=tmp_path, run_id="run-1")

    assert set(artifacts.as_dict()) == {
        "research_brief",
        "research_tasks",
        "evidence",
        "verification",
        "critique",
        "outline",
        "draft_report",
        "final_report",
        "report_json",
        "trace",
    }

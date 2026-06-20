import json
from datetime import datetime, timezone
from pathlib import Path

from traceresearch.evidence.models import ResearchRunStatus
from traceresearch.harness.run_state import RunState


def test_run_state_reads_completed_run_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    for name in [
        "research_brief.json",
        "research_tasks.json",
        "verification.json",
        "critique.json",
        "outline.md",
        "draft_report.md",
    ]:
        (run_dir / name).write_text("{}" if name.endswith(".json") else "", encoding="utf-8")
    (run_dir / "final_report.md").write_text("# report", encoding="utf-8")
    (run_dir / "report.json").write_text("{}", encoding="utf-8")
    (run_dir / "evidence.jsonl").write_text(
        json.dumps(
            {
                "evidence_id": "EV-run-1-001",
                "run_id": "run-1",
                "research_task_id": "task-1",
                "perspective": "technical",
                "source": {
                    "source_id": "src-1",
                    "provider": "fixture",
                    "title": "Source",
                    "url": None,
                    "source_type": "official_doc",
                    "publisher": "Publisher",
                    "published_at": None,
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "snippet": "Snippet",
                    "provider_rank": 1,
                },
                "authority_score": 0.9,
                "relevance_score": 0.9,
                "summary": "Summary",
                "key_points": ["Point"],
                "supported_claims": ["Claim"],
                "limitations": ["Limit"],
                "status": "verified",
                "verification_notes": ["Verified"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "trace.jsonl").write_text("", encoding="utf-8")

    state = RunState(run_dir)

    assert state.status() == ResearchRunStatus.COMPLETED
    assert state.evidence_by_id("EV-run-1-001") is not None
    assert state.report_paths().report_json == run_dir / "report.json"


def test_run_state_reads_needs_clarification_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-needs"
    run_dir.mkdir()
    (run_dir / "research_brief.json").write_text(
        json.dumps({"open_clarifications": ["Clarify object"]}),
        encoding="utf-8",
    )
    (run_dir / "trace.jsonl").write_text(
        json.dumps(
            {
                "trace_id": "TR-run-needs-001",
                "run_id": "run-needs",
                "task_id": None,
                "agent_role": "Planner",
                "event_type": "finish",
                "tool_name": None,
                "input_summary": "query",
                "output_summary": "needs clarification",
                "status": "needs_clarification",
                "latency_ms": 0,
                "token_usage": None,
                "error": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert RunState(run_dir).status() == ResearchRunStatus.NEEDS_CLARIFICATION


def test_run_state_reads_failed_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-failed"
    run_dir.mkdir()
    (run_dir / "trace.jsonl").write_text(
        json.dumps(
            {
                "trace_id": "TR-run-failed-001",
                "run_id": "run-failed",
                "task_id": None,
                "agent_role": "Harness",
                "event_type": "error",
                "tool_name": None,
                "input_summary": "run",
                "output_summary": "failed",
                "status": "failed",
                "latency_ms": 0,
                "token_usage": None,
                "error": {"type": "Error", "message": "failed"},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert RunState(run_dir).status() == ResearchRunStatus.FAILED

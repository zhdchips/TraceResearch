from datetime import datetime, timezone
from pathlib import Path

from traceresearch.trace.models import (
    AgentRole,
    ErrorInfo,
    EventType,
    TraceEvent,
    TraceStatus,
)
from traceresearch.trace.writer import TraceWriter


def _event(trace_id: str, event_type: EventType, status: TraceStatus) -> TraceEvent:
    error = None
    if status == TraceStatus.FAILED:
        error = ErrorInfo(type="ProviderError", message="provider failed")
    return TraceEvent(
        trace_id=trace_id,
        run_id="run-1",
        task_id="task-1",
        agent_role=AgentRole.HARNESS,
        event_type=event_type,
        tool_name=None,
        input_summary="input",
        output_summary="output",
        status=status,
        latency_ms=1,
        error=error,
        created_at=datetime.now(timezone.utc),
    )


def test_trace_writer_appends_and_reads_events(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"
    writer = TraceWriter(trace_path)
    start = _event("TR-run-1-001", EventType.START, TraceStatus.SUCCESS)
    finish = _event("TR-run-1-002", EventType.FINISH, TraceStatus.SUCCESS)

    writer.append(start)
    writer.append(finish)

    events = writer.read_all()

    assert [event.trace_id for event in events] == ["TR-run-1-001", "TR-run-1-002"]


def test_trace_writer_preserves_error_summary(tmp_path: Path) -> None:
    trace_path = tmp_path / "nested" / "trace.jsonl"
    writer = TraceWriter(trace_path)
    failed = _event("TR-run-1-003", EventType.ERROR, TraceStatus.FAILED)

    writer.append(failed)
    [event] = writer.read_all()

    assert event.error is not None
    assert event.error.message == "provider failed"


def test_trace_writer_lines_are_json(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"
    writer = TraceWriter(trace_path)
    writer.append(_event("TR-run-1-001", EventType.START, TraceStatus.SUCCESS))

    line = trace_path.read_text().strip()

    assert line.startswith("{")
    assert '"trace_id":"TR-run-1-001"' in line


def test_completed_run_trace_coverage_validates_required_roles(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"
    writer = TraceWriter(trace_path)
    for index, role in enumerate(
        [
            AgentRole.PLANNER,
            AgentRole.RESEARCHER,
            AgentRole.VERIFIER,
            AgentRole.CRITIC,
            AgentRole.WRITER,
            AgentRole.HARNESS,
        ],
        start=1,
    ):
        event = _event(f"TR-run-1-{index:03d}", EventType.FINISH, TraceStatus.SUCCESS)
        writer.append(event.model_copy(update={"agent_role": role}))

    writer.validate_completed_run_coverage()


def test_completed_run_trace_coverage_reports_missing_roles(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"
    writer = TraceWriter(trace_path)
    writer.append(
        _event("TR-run-1-001", EventType.FINISH, TraceStatus.SUCCESS).model_copy(
            update={"agent_role": AgentRole.PLANNER}
        )
    )

    try:
        writer.validate_completed_run_coverage()
    except ValueError as error:
        assert "Researcher" in str(error)
        assert "Harness" in str(error)
    else:  # pragma: no cover
        raise AssertionError("Expected missing Trace roles to fail coverage validation")

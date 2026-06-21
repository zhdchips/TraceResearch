from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from traceresearch.trace.models import (
    AgentRole,
    ErrorInfo,
    EventType,
    TokenUsage,
    TraceEvent,
    TraceStatus,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_trace_event_serializes_enum_values() -> None:
    event = TraceEvent(
        trace_id="TR-run-1-001",
        run_id="run-1",
        task_id="task-1",
        agent_role=AgentRole.PLANNER,
        event_type=EventType.START,
        tool_name=None,
        input_summary="query",
        output_summary="started",
        status=TraceStatus.SUCCESS,
        latency_ms=0,
        created_at=_now(),
    )

    payload = event.model_dump(mode="json")

    assert payload["agent_role"] == "Planner"
    assert payload["event_type"] == "start"
    assert payload["status"] == "success"


def test_failed_trace_event_requires_error_message() -> None:
    with pytest.raises(ValidationError, match="error.message"):
        TraceEvent(
            trace_id="TR-run-1-002",
            run_id="run-1",
            agent_role=AgentRole.RESEARCHER,
            event_type=EventType.ERROR,
            input_summary="search",
            output_summary="failed",
            status=TraceStatus.FAILED,
            latency_ms=10,
            error=ErrorInfo(type="ProviderError"),
            created_at=_now(),
        )


def test_latency_and_token_usage_are_validated() -> None:
    with pytest.raises(ValidationError):
        TraceEvent(
            trace_id="TR-run-1-003",
            run_id="run-1",
            agent_role=AgentRole.WRITER,
            event_type=EventType.FINISH,
            input_summary="evidence",
            output_summary="report",
            status=TraceStatus.SUCCESS,
            latency_ms=-1,
            token_usage=TokenUsage(total_tokens=1),
            created_at=_now(),
        )

    usage = TokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3)

    assert usage.total_tokens == 3


def test_all_agent_roles_are_available() -> None:
    assert {role.value for role in AgentRole} == {
        "Planner",
        "Researcher",
        "ResearchLead",
        "ResearchSubagent",
        "Verifier",
        "Critic",
        "Writer",
        "EvalRunner",
        "Harness",
        "LeadRuntime",
        "LangGraph",
    }

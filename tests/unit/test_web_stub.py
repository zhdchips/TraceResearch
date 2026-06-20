from datetime import datetime, timezone

import pytest

from traceresearch.evidence.models import ResearchTask, ResearchTaskStatus
from traceresearch.source_discovery.base import (
    ProviderNotConfiguredError,
    SourceRef,
)
from traceresearch.source_discovery.web_stub import WebSearchProviderStub
from traceresearch.trace.models import AgentRole, EventType, TraceEvent, TraceStatus


def _task() -> ResearchTask:
    return ResearchTask(
        research_task_id="task-1",
        run_id="run-1",
        perspective="technical",
        objective="Find current web sources",
        query="agent runtime web search",
        status=ResearchTaskStatus.PENDING,
        source_limit=3,
    )


def test_web_search_stub_search_returns_provider_not_configured() -> None:
    provider = WebSearchProviderStub()

    with pytest.raises(ProviderNotConfiguredError) as exc_info:
        provider.search(_task(), limit=3)

    assert exc_info.value.code == "provider_not_configured"
    assert exc_info.value.provider_name == "web"


def test_web_search_stub_fetch_returns_provider_not_configured() -> None:
    provider = WebSearchProviderStub()

    with pytest.raises(ProviderNotConfiguredError) as exc_info:
        provider.fetch(SourceRef(source_id="web-src-1", url="https://example.test"))

    assert exc_info.value.code == "provider_not_configured"
    assert "web" in str(exc_info.value)


def test_web_search_stub_error_info_can_build_trace_error_event() -> None:
    provider = WebSearchProviderStub()

    try:
        provider.search(_task(), limit=1)
    except ProviderNotConfiguredError as error:
        payload = provider.trace_error_payload(error, operation="search")
    else:  # pragma: no cover
        raise AssertionError("web stub search should fail when unconfigured")

    event = TraceEvent(
        trace_id="TR-run-1-001",
        run_id="run-1",
        task_id="task-1",
        agent_role=AgentRole.RESEARCHER,
        event_type=EventType.ERROR,
        tool_name=payload.tool_name,
        input_summary="web search",
        output_summary=payload.output_summary,
        status=payload.status,
        latency_ms=0,
        error=payload.error,
        created_at=datetime.now(timezone.utc),
    )

    assert event.status == TraceStatus.FAILED
    assert event.error is not None
    assert event.error.type == "provider_not_configured"
    assert "web" in event.error.message


def test_web_search_stub_does_not_silently_fallback_to_fixture() -> None:
    provider = WebSearchProviderStub()

    with pytest.raises(ProviderNotConfiguredError):
        provider.search(
            ResearchTask(
                research_task_id="001-framework-comparison-task",
                run_id="001-framework-comparison",
                perspective="orchestration model",
                objective="Find fixture-like sources",
                query="Compare LangGraph AutoGen CrewAI",
                status=ResearchTaskStatus.PENDING,
                source_limit=5,
            ),
            limit=5,
        )

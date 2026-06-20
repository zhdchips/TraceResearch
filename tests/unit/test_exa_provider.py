from datetime import date

import pytest

from traceresearch.evidence.models import ResearchTask, ResearchTaskStatus, SourceType
from traceresearch.source_discovery.base import SourceRef


def _task() -> ResearchTask:
    return ResearchTask(
        research_task_id="task-live-1",
        run_id="run-live-1",
        perspective="market and technical changes",
        objective="Find current public sources",
        query="What changed in AI coding agents during the last 12 months?",
        status=ResearchTaskStatus.PENDING,
        source_limit=5,
    )


def test_exa_search_provider_normalizes_search_results(monkeypatch: pytest.MonkeyPatch) -> None:
    from traceresearch.config import LiveProviderConfig
    from traceresearch.source_discovery.exa_provider import ExaSearchProvider

    monkeypatch.setenv("EXA_API_KEY", "test-exa-secret")
    config = LiveProviderConfig.from_env()
    provider = ExaSearchProvider(config=config)

    payload = {
        "requestId": "exa-request-123",
        "costDollars": {"total": 0.002},
        "results": [
            {
                "id": "result-1",
                "title": "AI coding agents shift from autocomplete to delegated work",
                "url": "https://example.com/ai-coding-agents",
                "publishedDate": "2026-03-15",
                "author": "Example Research",
                "text": "Longer extracted body about coding agents and runtimes.",
                "highlights": ["Agentic coding tools increasingly run delegated tasks."],
                "summary": "AI coding agents moved from suggestions toward delegated tasks.",
                "score": 0.93,
            }
        ],
    }

    monkeypatch.setattr(provider, "_post_search", lambda _body: payload)

    results = provider.search(_task(), limit=5)

    assert len(results) == 1
    result = results[0]
    assert result.provider == "web"
    assert result.title.startswith("AI coding agents")
    assert str(result.url) == "https://example.com/ai-coding-agents"
    assert result.source_type in SourceType
    assert result.published_at == date(2026, 3, 15)
    assert result.provider_rank == 1
    assert "delegated tasks" in result.snippet


def test_exa_search_provider_fetch_returns_cached_normalized_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from traceresearch.config import LiveProviderConfig
    from traceresearch.source_discovery.exa_provider import ExaSearchProvider

    monkeypatch.setenv("EXA_API_KEY", "test-exa-secret")
    provider = ExaSearchProvider(config=LiveProviderConfig.from_env())
    monkeypatch.setattr(
        provider,
        "_post_search",
        lambda _body: {
            "requestId": "exa-request-123",
            "results": [
                {
                    "id": "result-1",
                    "title": "OpenHands runtime documentation",
                    "url": "https://example.com/openhands-runtime",
                    "text": "Runtime details for isolated agent execution.",
                    "highlights": ["OpenHands isolates agent execution in runtime containers."],
                    "summary": "OpenHands runtime supports isolated execution.",
                }
            ],
        },
    )

    source = provider.search(_task(), limit=1)[0]
    document = provider.fetch(SourceRef(source_id=source.source_id, url=source.url))

    assert document.source_id == source.source_id
    assert document.title == source.title
    assert "isolated execution" in document.content_excerpt
    assert document.metadata["provider"] == "web"
    assert document.metadata["provider_name"] == "exa"
    assert document.metadata["provider_request_id"] == "exa-request-123"


def test_exa_search_provider_empty_results_maps_to_provider_no_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from traceresearch.config import LiveProviderConfig
    from traceresearch.source_discovery.base import ProviderNoResultsError
    from traceresearch.source_discovery.exa_provider import ExaSearchProvider

    monkeypatch.setenv("EXA_API_KEY", "test-exa-secret")
    provider = ExaSearchProvider(config=LiveProviderConfig.from_env())
    monkeypatch.setattr(provider, "_post_search", lambda _body: {"results": []})

    with pytest.raises(ProviderNoResultsError) as exc_info:
        provider.search(_task(), limit=5)

    assert exc_info.value.code == "provider_no_results"


def test_exa_search_provider_rejects_unusable_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    from traceresearch.config import LiveProviderConfig
    from traceresearch.source_discovery.base import SourceNormalizationError
    from traceresearch.source_discovery.exa_provider import ExaSearchProvider

    monkeypatch.setenv("EXA_API_KEY", "test-exa-secret")
    provider = ExaSearchProvider(config=LiveProviderConfig.from_env())
    monkeypatch.setattr(
        provider,
        "_post_search",
        lambda _body: {"results": [{"id": "bad-result", "score": 0.1}]},
    )

    with pytest.raises(SourceNormalizationError) as exc_info:
        provider.search(_task(), limit=5)

    assert exc_info.value.code == "source_normalization_error"

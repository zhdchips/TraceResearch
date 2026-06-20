from datetime import datetime, timezone

import pytest

from traceresearch.evidence.models import (
    ResearchTask,
    ResearchTaskStatus,
    SourceDocument,
    SourceResult,
    SourceType,
)
from traceresearch.source_discovery.base import (
    ProviderNotConfiguredError,
    SourceDiscoveryError,
    SourceDiscoveryProvider,
    SourceRef,
)


class FakeProvider(SourceDiscoveryProvider):
    provider_name = "fake"

    def search(self, task: ResearchTask, limit: int) -> list[SourceResult]:
        return [
            SourceResult(
                source_id="src-1",
                provider=self.provider_name,
                title=f"Result for {task.query}",
                source_type=SourceType.OFFICIAL_DOC,
                retrieved_at=datetime.now(timezone.utc),
                snippet="snippet",
                provider_rank=1,
            )
        ][:limit]

    def fetch(self, source_ref: SourceRef) -> SourceDocument:
        return SourceDocument(
            source_id=source_ref.source_id,
            title="Fetched",
            content_excerpt="excerpt",
            metadata={"provider": self.provider_name},
            retrieved_at=datetime.now(timezone.utc),
        )


def _task() -> ResearchTask:
    return ResearchTask(
        research_task_id="task-1",
        run_id="run-1",
        perspective="technical",
        objective="Find source",
        query="agent runtime",
        status=ResearchTaskStatus.PENDING,
        source_limit=3,
    )


def test_source_provider_contract_search_and_fetch() -> None:
    provider = FakeProvider()
    [result] = provider.search(_task(), limit=1)
    document = provider.fetch(SourceRef(source_id=result.source_id, url=result.url))

    assert result.provider == "fake"
    assert document.source_id == "src-1"


def test_source_ref_requires_identifier() -> None:
    with pytest.raises(ValueError):
        SourceRef(source_id="")


def test_provider_not_configured_error_has_stable_code() -> None:
    error = ProviderNotConfiguredError("web")

    assert isinstance(error, SourceDiscoveryError)
    assert error.code == "provider_not_configured"
    assert "web" in str(error)

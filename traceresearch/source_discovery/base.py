"""Source discovery provider contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from pydantic import HttpUrl

from traceresearch.evidence.models import ResearchTask, SourceDocument, SourceResult


@dataclass(frozen=True)
class SourceRef:
    source_id: str
    url: HttpUrl | str | None = None

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id is required")


class SourceDiscoveryError(RuntimeError):
    code = "source_discovery_error"


class ProviderNotConfiguredError(SourceDiscoveryError):
    code = "provider_not_configured"

    def __init__(self, provider_name: str) -> None:
        super().__init__(f"Source discovery provider is not configured: {provider_name}")
        self.provider_name = provider_name


class SourceDiscoveryProvider(ABC):
    provider_name: str

    @abstractmethod
    def search(self, task: ResearchTask, limit: int) -> list[SourceResult]:
        """Return ordered source results for a research task."""

    @abstractmethod
    def fetch(self, source_ref: SourceRef) -> SourceDocument:
        """Return a normalized source document for a source reference."""

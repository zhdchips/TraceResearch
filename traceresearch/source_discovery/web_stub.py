"""Not-configured web source discovery provider for the MVP."""

from __future__ import annotations

from dataclasses import dataclass

from traceresearch.evidence.models import ResearchTask, SourceDocument, SourceResult
from traceresearch.source_discovery.base import (
    ProviderNotConfiguredError,
    SourceRef,
    SourceDiscoveryProvider,
)
from traceresearch.trace.models import ErrorInfo, TraceStatus


@dataclass(frozen=True)
class WebProviderTraceErrorPayload:
    tool_name: str
    output_summary: str
    status: TraceStatus
    error: ErrorInfo


class WebSearchProviderStub(SourceDiscoveryProvider):
    """Explicit stub for future live web search integration."""

    provider_name = "web"
    tool_name = "web_search"

    def search(self, task: ResearchTask, limit: int) -> list[SourceResult]:
        raise self.not_configured_error()

    def fetch(self, source_ref: SourceRef) -> SourceDocument:
        raise self.not_configured_error()

    def not_configured_error(self) -> ProviderNotConfiguredError:
        return ProviderNotConfiguredError(self.provider_name)

    def trace_error_payload(
        self,
        error: ProviderNotConfiguredError | None = None,
        *,
        operation: str,
    ) -> WebProviderTraceErrorPayload:
        resolved_error = error or self.not_configured_error()
        return WebProviderTraceErrorPayload(
            tool_name=self.tool_name,
            output_summary=(
                f"{self.provider_name} provider {operation} failed: "
                f"{resolved_error.code}"
            ),
            status=TraceStatus.FAILED,
            error=ErrorInfo(type=resolved_error.code, message=str(resolved_error)),
        )

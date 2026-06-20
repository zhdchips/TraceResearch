"""Source discovery provider contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import re

from pydantic import HttpUrl

from traceresearch.evidence.models import ResearchTask, SourceDocument, SourceResult
from traceresearch.trace.models import ErrorInfo


@dataclass(frozen=True)
class SourceRef:
    source_id: str
    url: HttpUrl | str | None = None

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id is required")


class SourceDiscoveryError(RuntimeError):
    code = "source_discovery_error"


class ProviderError(SourceDiscoveryError):
    def __init__(
        self,
        *,
        code: str,
        provider_name: str,
        operation: str,
        message: str,
        retryable: bool = False,
        status_code: int | None = None,
        latency_ms: int | None = None,
    ) -> None:
        self.code = code
        self.provider_name = provider_name
        self.operation = operation
        self.retryable = retryable
        self.status_code = status_code
        self.latency_ms = latency_ms
        self.message = _redact_secret_markers(message)
        super().__init__(self.message)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(code={self.code!r}, "
            f"provider_name={self.provider_name!r}, operation={self.operation!r}, "
            f"message={self.message!r})"
        )

    def to_trace_error(self) -> ErrorInfo:
        details = [self.message]
        if self.status_code is not None:
            details.append(f"status_code={self.status_code}")
        if self.retryable:
            details.append("retryable=true")
        return ErrorInfo(type=self.code, message="; ".join(details))


class ProviderTimeoutError(ProviderError):
    def __init__(
        self,
        provider_name: str,
        operation: str,
        *,
        message: str = "Provider request timed out.",
        latency_ms: int | None = None,
    ) -> None:
        super().__init__(
            code="provider_timeout",
            provider_name=provider_name,
            operation=operation,
            message=message,
            retryable=True,
            latency_ms=latency_ms,
        )


class ProviderRateLimitedError(ProviderError):
    def __init__(
        self,
        provider_name: str,
        operation: str,
        *,
        message: str = "Provider rate limit exceeded.",
        status_code: int | None = 429,
    ) -> None:
        super().__init__(
            code="provider_rate_limited",
            provider_name=provider_name,
            operation=operation,
            message=message,
            retryable=True,
            status_code=status_code,
        )


class ProviderServiceError(ProviderError):
    def __init__(
        self,
        provider_name: str,
        operation: str,
        *,
        message: str = "Provider request failed.",
        status_code: int | None = None,
        retryable: bool = True,
    ) -> None:
        super().__init__(
            code="provider_error",
            provider_name=provider_name,
            operation=operation,
            message=message,
            retryable=retryable,
            status_code=status_code,
        )


class ProviderNoResultsError(ProviderError):
    def __init__(
        self,
        provider_name: str,
        operation: str = "search",
        *,
        message: str = "Provider returned no results.",
    ) -> None:
        super().__init__(
            code="provider_no_results",
            provider_name=provider_name,
            operation=operation,
            message=message,
            retryable=False,
        )


class SourceNormalizationError(ProviderError):
    def __init__(
        self,
        provider_name: str,
        operation: str = "search",
        *,
        message: str = "Provider result could not be normalized.",
    ) -> None:
        super().__init__(
            code="source_normalization_error",
            provider_name=provider_name,
            operation=operation,
            message=message,
            retryable=False,
        )


class ProviderNotConfiguredError(SourceDiscoveryError):
    code = "provider_not_configured"

    def __init__(self, provider_name: str) -> None:
        super().__init__(f"Source discovery provider is not configured: {provider_name}")
        self.provider_name = provider_name

    def to_trace_error(self) -> ErrorInfo:
        return ErrorInfo(type=self.code, message=str(self))


class SourceDiscoveryProvider(ABC):
    provider_name: str

    @abstractmethod
    def search(self, task: ResearchTask, limit: int) -> list[SourceResult]:
        """Return ordered source results for a research task."""

    @abstractmethod
    def fetch(self, source_ref: SourceRef) -> SourceDocument:
        """Return a normalized source document for a source reference."""


def _redact_secret_markers(message: str) -> str:
    redacted = message.replace("EXA_API_KEY", "[redacted]")
    for marker in ("exa_live_", "test-exa-secret", "exa_live_secret", "x-api-key"):
        if marker in redacted:
            redacted = redacted.replace(marker, "[redacted]")
    redacted = re.sub(r"exa_live_[A-Za-z0-9_:-]+", "[redacted]", redacted)
    redacted = re.sub(r"sk-[A-Za-z0-9_-]+", "[redacted]", redacted)
    return redacted

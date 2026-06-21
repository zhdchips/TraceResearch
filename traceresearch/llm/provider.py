"""LLMProvider abstract base class and error model."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class LLMProviderError(Exception):
    """Raised when an LLM provider call fails.

    Attributes:
        reason: Machine-readable failure category.
            One of "no_api_key", "timeout", "rate_limit",
            "invalid_response", "provider_error".
        provider: Provider name (e.g. "deepseek").
        model: Model ID (e.g. "deepseek-chat").
        latency_ms: Round-trip latency in milliseconds.
    """

    def __init__(self, reason: str, provider: str, model: str, latency_ms: float) -> None:
        self.reason = reason
        self.provider = provider
        self.model = model
        self.latency_ms = latency_ms
        super().__init__(
            f"LLM call failed: {reason} (provider={provider}, model={model}, "
            f"latency={latency_ms:.0f}ms)"
        )


class LLMProvider(ABC):
    """Vendor-agnostic LLM provider abstraction.

    Implementations MUST handle:
    - HTTP-level failures (timeout, 4xx, 5xx) → LLMProviderError
    - Response parsing failures → LLMProviderError
    - Schema validation → return validated BaseModel instance
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier (e.g. "deepseek")."""
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        """Model identifier (e.g. "deepseek-chat")."""
        ...

    @abstractmethod
    def complete(
        self,
        prompt: str,
        response_schema: type[BaseModel],
        system_prompt: str | None = None,
    ) -> BaseModel:
        """Call the LLM and return a schema-validated response.

        Args:
            prompt: User message content.
            response_schema: Pydantic model class for parsing LLM output.
            system_prompt: Optional system-level instruction.

        Returns:
            An instance of ``response_schema``.

        Raises:
            LLMProviderError: On any failure (timeout, rate limit,
                invalid response, schema mismatch, provider error).
        """
        ...

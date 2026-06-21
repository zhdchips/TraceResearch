"""DeepSeek LLM provider — OpenAI-compatible chat completions API."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import httpx
from pydantic import BaseModel

from traceresearch.llm.provider import LLMProvider, LLMProviderError
from traceresearch.trace.models import TokenUsage


class DeepSeekProvider(LLMProvider):
    """Calls DeepSeek API via OpenAI-compatible /v1/chat/completions.

    Does NOT retry on failure — retry policy is the caller's responsibility
    (typically: fallback to deterministic Writer/Verifier).

    Token usage from the last successful call is exposed via
    ``last_token_usage`` for Trace recording.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com",
        timeout_seconds: float = 60.0,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._last_token_usage: TokenUsage | None = None

    # ------------------------------------------------------------------
    # LLMProvider interface
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        return "deepseek"

    @property
    def model(self) -> str:
        return self._model

    @property
    def last_token_usage(self) -> TokenUsage | None:
        """Token usage from the most recent successful call, if any."""
        return self._last_token_usage

    def complete(
        self,
        prompt: str,
        response_schema: type[BaseModel],
        system_prompt: str | None = None,
    ) -> BaseModel:
        start = time.monotonic()

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self._base_url}/v1/chat/completions"

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(url, headers=headers, content=json.dumps(body))
        except httpx.TimeoutException:
            latency = (time.monotonic() - start) * 1000
            raise LLMProviderError(
                reason="timeout",
                provider=self.provider_name,
                model=self._model,
                latency_ms=latency,
            )

        latency_ms = (time.monotonic() - start) * 1000

        if resp.status_code == 429:
            raise LLMProviderError(
                reason="rate_limit",
                provider=self.provider_name,
                model=self._model,
                latency_ms=latency_ms,
            )

        if resp.status_code >= 400:
            raise LLMProviderError(
                reason="provider_error",
                provider=self.provider_name,
                model=self._model,
                latency_ms=latency_ms,
            )

        # Parse OpenAI-compatible response
        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
            raise LLMProviderError(
                reason="invalid_response",
                provider=self.provider_name,
                model=self._model,
                latency_ms=latency_ms,
            )

        choices = data.get("choices")
        if not choices or not isinstance(choices, list):
            raise LLMProviderError(
                reason="invalid_response",
                provider=self.provider_name,
                model=self._model,
                latency_ms=latency_ms,
            )

        content = choices[0].get("message", {}).get("content", "")

        # Parse LLM output against schema
        try:
            parsed = response_schema.model_validate_json(content)
        except Exception:
            raise LLMProviderError(
                reason="invalid_response",
                provider=self.provider_name,
                model=self._model,
                latency_ms=latency_ms,
            )

        # Record token usage
        usage_raw = data.get("usage", {})
        if usage_raw:
            self._last_token_usage = TokenUsage(
                prompt_tokens=usage_raw.get("prompt_tokens"),
                completion_tokens=usage_raw.get("completion_tokens"),
                total_tokens=usage_raw.get("total_tokens"),
            )

        return parsed

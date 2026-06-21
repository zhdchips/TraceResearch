"""LLM provider configuration — reads from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

# Provider-specific fallback environment variable names.
# When TRACERESEARCH_LLM_API_KEY is not set, the provider-specific var is checked.
_FALLBACK_KEY_ENV_VARS: dict[str, str] = {
    "deepseek": "DEEPSEEK_API_KEY",
}


@dataclass
class LLMProviderConfig:
    """Immutable configuration for an LLM provider.

    Reads from TRACERESEARCH_LLM_* env vars with sensible DeepSeek defaults.
    Missing API key is NOT an error — callers check ``is_configured()``.
    """

    provider: str
    api_key: str
    model: str
    base_url: str
    timeout_seconds: float = 60.0
    max_tokens: int = 4096
    temperature: float = 0.0

    @classmethod
    def from_env(cls) -> LLMProviderConfig:
        provider = os.environ.get("TRACERESEARCH_LLM_PROVIDER", "deepseek")

        api_key = os.environ.get("TRACERESEARCH_LLM_API_KEY", "")
        if not api_key:
            fallback_var = _FALLBACK_KEY_ENV_VARS.get(provider, "")
            if fallback_var:
                api_key = os.environ.get(fallback_var, "")

        model = os.environ.get("TRACERESEARCH_LLM_MODEL", "deepseek-chat")
        base_url = os.environ.get("TRACERESEARCH_LLM_BASE_URL", "https://api.deepseek.com")

        timeout_str = os.environ.get("TRACERESEARCH_LLM_TIMEOUT", "60")
        try:
            timeout_seconds = float(timeout_str)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid TRACERESEARCH_LLM_TIMEOUT: {timeout_str!r}")

        max_tokens_str = os.environ.get("TRACERESEARCH_LLM_MAX_TOKENS", "4096")
        try:
            max_tokens = int(max_tokens_str)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid TRACERESEARCH_LLM_MAX_TOKENS: {max_tokens_str!r}")
        if max_tokens < 1:
            raise ValueError(f"TRACERESEARCH_LLM_MAX_TOKENS must be >= 1, got {max_tokens}")

        temperature_str = os.environ.get("TRACERESEARCH_LLM_TEMPERATURE", "0.0")
        try:
            temperature = float(temperature_str)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid TRACERESEARCH_LLM_TEMPERATURE: {temperature_str!r}")

        return cls(
            provider=provider,
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def is_configured(self) -> bool:
        """Return True if an API key is available."""
        return bool(self.api_key)

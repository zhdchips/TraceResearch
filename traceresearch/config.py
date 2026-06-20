"""Configuration helpers for TraceResearch live providers."""

from __future__ import annotations

import os
from dataclasses import dataclass

from traceresearch.source_discovery.base import ProviderNotConfiguredError


DEFAULT_WEB_PROVIDER = "exa"
DEFAULT_WEB_TIMEOUT_SECONDS = 10.0
DEFAULT_WEB_MAX_RESULTS = 5
DEFAULT_EXA_BASE_URL = "https://api.exa.ai"


@dataclass(frozen=True)
class LiveProviderConfig:
    provider_name: str = DEFAULT_WEB_PROVIDER
    api_key: str | None = None
    timeout_seconds: float = DEFAULT_WEB_TIMEOUT_SECONDS
    max_results: int = DEFAULT_WEB_MAX_RESULTS
    base_url: str = DEFAULT_EXA_BASE_URL

    @classmethod
    def from_env(cls) -> "LiveProviderConfig":
        provider_name = _read_str("TRACERESEARCH_WEB_PROVIDER", DEFAULT_WEB_PROVIDER)
        api_key = os.environ.get("EXA_API_KEY")
        timeout_seconds = _read_positive_float(
            "TRACERESEARCH_WEB_TIMEOUT_SECONDS",
            DEFAULT_WEB_TIMEOUT_SECONDS,
        )
        max_results = _read_positive_int(
            "TRACERESEARCH_WEB_MAX_RESULTS",
            DEFAULT_WEB_MAX_RESULTS,
        )
        return cls(
            provider_name=provider_name,
            api_key=api_key.strip() if api_key and api_key.strip() else None,
            timeout_seconds=timeout_seconds,
            max_results=max_results,
        )

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    def require_configured(self) -> None:
        if not self.has_api_key:
            raise ProviderNotConfiguredError(self.provider_name)

    def __repr__(self) -> str:
        return (
            "LiveProviderConfig("
            f"provider_name={self.provider_name!r}, "
            f"has_api_key={self.has_api_key}, "
            f"timeout_seconds={self.timeout_seconds!r}, "
            f"max_results={self.max_results!r}, "
            f"base_url={self.base_url!r}"
            ")"
        )


def _read_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else default


def _read_positive_float(name: str, default: float) -> float:
    raw_value = os.environ.get(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive number") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive number")
    return value


def _read_positive_int(name: str, default: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value

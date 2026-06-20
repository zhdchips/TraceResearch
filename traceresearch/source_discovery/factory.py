"""Source discovery provider factory."""

from __future__ import annotations

from traceresearch.config import LiveProviderConfig
from traceresearch.source_discovery.base import (
    ProviderNotConfiguredError,
    SourceDiscoveryError,
    SourceDiscoveryProvider,
)
from traceresearch.source_discovery.exa_provider import ExaSearchProvider
from traceresearch.source_discovery.fixture_provider import FixtureSourceProvider


def build_source_provider(
    *,
    source_provider: str,
    case_id: str | None = None,
    config: LiveProviderConfig | None = None,
) -> SourceDiscoveryProvider:
    provider = source_provider.strip().lower()
    if provider == "fixture":
        return FixtureSourceProvider(case_id=case_id)
    if provider == "web":
        live_config = config or LiveProviderConfig.from_env()
        if live_config.provider_name != "exa":
            raise ProviderNotConfiguredError(live_config.provider_name)
        live_config.require_configured()
        return ExaSearchProvider(config=live_config)
    raise SourceDiscoveryError(f"Unsupported source provider: {source_provider}")

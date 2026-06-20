import pytest


def test_provider_factory_returns_fixture_provider_for_fixture() -> None:
    from traceresearch.source_discovery.factory import build_source_provider
    from traceresearch.source_discovery.fixture_provider import FixtureSourceProvider

    provider = build_source_provider(
        source_provider="fixture",
        case_id="001-framework-comparison",
    )

    assert isinstance(provider, FixtureSourceProvider)
    assert provider.provider_name == "fixture"


def test_provider_factory_web_without_key_fails_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from traceresearch.source_discovery.base import ProviderNotConfiguredError
    from traceresearch.source_discovery.factory import build_source_provider

    monkeypatch.setenv("TRACERESEARCH_WEB_PROVIDER", "exa")
    monkeypatch.delenv("EXA_API_KEY", raising=False)

    with pytest.raises(ProviderNotConfiguredError) as exc_info:
        build_source_provider(source_provider="web")

    assert exc_info.value.code == "provider_not_configured"
    assert exc_info.value.provider_name in {"web", "exa"}


def test_provider_factory_web_with_key_returns_exa_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from traceresearch.source_discovery.exa_provider import ExaSearchProvider
    from traceresearch.source_discovery.factory import build_source_provider

    monkeypatch.setenv("TRACERESEARCH_WEB_PROVIDER", "exa")
    monkeypatch.setenv("EXA_API_KEY", "test-exa-secret")

    provider = build_source_provider(source_provider="web")

    assert isinstance(provider, ExaSearchProvider)
    assert provider.provider_name == "web"
    assert provider.provider_display_name == "exa"


def test_provider_factory_unsupported_provider_fails_clearly() -> None:
    from traceresearch.source_discovery.base import SourceDiscoveryError
    from traceresearch.source_discovery.factory import build_source_provider

    with pytest.raises(SourceDiscoveryError) as exc_info:
        build_source_provider(source_provider="unknown")

    assert "unknown" in str(exc_info.value)


def test_provider_factory_never_falls_back_to_fixture_for_web_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from traceresearch.source_discovery.base import ProviderNotConfiguredError
    from traceresearch.source_discovery.factory import build_source_provider

    monkeypatch.setenv("TRACERESEARCH_WEB_PROVIDER", "exa")
    monkeypatch.setenv("EXA_API_KEY", "")

    with pytest.raises(ProviderNotConfiguredError) as exc_info:
        build_source_provider(
            source_provider="web",
            case_id="001-framework-comparison",
        )

    assert exc_info.value.code == "provider_not_configured"

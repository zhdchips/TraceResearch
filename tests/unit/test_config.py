import pytest


def test_live_provider_config_defaults_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from traceresearch.config import LiveProviderConfig

    monkeypatch.delenv("TRACERESEARCH_WEB_PROVIDER", raising=False)
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv("TRACERESEARCH_WEB_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("TRACERESEARCH_WEB_MAX_RESULTS", raising=False)

    config = LiveProviderConfig.from_env()

    assert config.provider_name == "exa"
    assert config.has_api_key is False
    assert config.timeout_seconds == 10
    assert config.max_results == 5


def test_live_provider_config_reads_exa_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    from traceresearch.config import LiveProviderConfig

    monkeypatch.setenv("TRACERESEARCH_WEB_PROVIDER", "exa")
    monkeypatch.setenv("EXA_API_KEY", "test-exa-secret")
    monkeypatch.setenv("TRACERESEARCH_WEB_TIMEOUT_SECONDS", "7.5")
    monkeypatch.setenv("TRACERESEARCH_WEB_MAX_RESULTS", "3")

    config = LiveProviderConfig.from_env()

    assert config.provider_name == "exa"
    assert config.has_api_key is True
    assert config.timeout_seconds == 7.5
    assert config.max_results == 3


def test_live_provider_config_missing_or_blank_key_maps_to_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from traceresearch.config import LiveProviderConfig
    from traceresearch.source_discovery.base import ProviderNotConfiguredError

    monkeypatch.setenv("TRACERESEARCH_WEB_PROVIDER", "exa")
    monkeypatch.setenv("EXA_API_KEY", "   ")

    config = LiveProviderConfig.from_env()

    assert config.has_api_key is False
    with pytest.raises(ProviderNotConfiguredError) as exc_info:
        config.require_configured()
    assert exc_info.value.code == "provider_not_configured"
    assert exc_info.value.provider_name == "exa"


@pytest.mark.parametrize(
    ("env_name", "env_value"),
    [
        ("TRACERESEARCH_WEB_TIMEOUT_SECONDS", "0"),
        ("TRACERESEARCH_WEB_TIMEOUT_SECONDS", "-1"),
        ("TRACERESEARCH_WEB_TIMEOUT_SECONDS", "not-a-number"),
        ("TRACERESEARCH_WEB_MAX_RESULTS", "0"),
        ("TRACERESEARCH_WEB_MAX_RESULTS", "-3"),
        ("TRACERESEARCH_WEB_MAX_RESULTS", "not-an-int"),
    ],
)
def test_live_provider_config_rejects_invalid_numeric_values(
    monkeypatch: pytest.MonkeyPatch,
    env_name: str,
    env_value: str,
) -> None:
    from traceresearch.config import LiveProviderConfig

    monkeypatch.setenv("EXA_API_KEY", "test-exa-secret")
    monkeypatch.setenv(env_name, env_value)

    with pytest.raises(ValueError) as exc_info:
        LiveProviderConfig.from_env()

    assert "test-exa-secret" not in str(exc_info.value)


def test_live_provider_config_redacts_secret_from_repr_and_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from traceresearch.config import LiveProviderConfig

    secret = "exa_live_super_secret"
    monkeypatch.setenv("EXA_API_KEY", secret)
    monkeypatch.setenv("TRACERESEARCH_WEB_TIMEOUT_SECONDS", "bad-timeout")

    with pytest.raises(ValueError) as exc_info:
        LiveProviderConfig.from_env()
    assert secret not in str(exc_info.value)

    monkeypatch.setenv("TRACERESEARCH_WEB_TIMEOUT_SECONDS", "10")
    config = LiveProviderConfig.from_env()
    assert secret not in repr(config)
    assert "has_api_key=True" in repr(config)

import pytest


def test_missing_key_error_is_safe_for_cli_and_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    from traceresearch.source_discovery.base import ProviderNotConfiguredError
    from traceresearch.source_discovery.factory import build_source_provider

    monkeypatch.setenv("TRACERESEARCH_WEB_PROVIDER", "exa")
    monkeypatch.delenv("EXA_API_KEY", raising=False)

    with pytest.raises(ProviderNotConfiguredError) as exc_info:
        build_source_provider(source_provider="web")

    assert exc_info.value.code == "provider_not_configured"
    assert "EXA_API_KEY" not in str(exc_info.value)


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [
        (401, "provider_not_configured"),
        (403, "provider_not_configured"),
        (429, "provider_rate_limited"),
        (500, "provider_error"),
        (503, "provider_error"),
    ],
)
def test_exa_http_errors_map_to_safe_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    expected_code: str,
) -> None:
    from traceresearch.config import LiveProviderConfig
    from traceresearch.source_discovery.exa_provider import ExaSearchProvider

    secret = "exa_live_secret_for_redaction"
    monkeypatch.setenv("EXA_API_KEY", secret)
    provider = ExaSearchProvider(config=LiveProviderConfig.from_env())

    with pytest.raises(Exception) as exc_info:
        provider._raise_for_http_status(status_code, "safe provider body")

    error = exc_info.value
    assert getattr(error, "code") == expected_code
    assert secret not in str(error)
    assert "x-api-key" not in str(error).lower()


def test_exa_timeout_maps_to_retryable_timeout_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from traceresearch.config import LiveProviderConfig
    from traceresearch.evidence.models import ResearchTask, ResearchTaskStatus
    from traceresearch.source_discovery.base import ProviderTimeoutError
    from traceresearch.source_discovery.exa_provider import ExaSearchProvider

    monkeypatch.setenv("EXA_API_KEY", "test-exa-secret")
    provider = ExaSearchProvider(config=LiveProviderConfig.from_env())

    def raise_timeout(_body: dict[str, object]) -> dict[str, object]:
        raise TimeoutError("network timed out with test-exa-secret")

    monkeypatch.setattr(provider, "_post_search", raise_timeout)

    with pytest.raises(ProviderTimeoutError) as exc_info:
        provider.search(
            ResearchTask(
                research_task_id="task-timeout",
                run_id="run-timeout",
                perspective="technical",
                objective="Find live sources",
                query="AI coding agents",
                status=ResearchTaskStatus.PENDING,
                source_limit=3,
            ),
            limit=3,
        )

    assert exc_info.value.code == "provider_timeout"
    assert exc_info.value.retryable is True
    assert "test-exa-secret" not in str(exc_info.value)


def test_provider_errors_have_structured_trace_payload_without_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from traceresearch.source_discovery.base import ProviderError

    secret = "exa_live_secret_for_redaction"
    monkeypatch.setenv("EXA_API_KEY", secret)

    error = ProviderError(
        code="provider_error",
        provider_name="exa",
        operation="search",
        message=f"upstream failed while using {secret}",
        retryable=True,
        status_code=502,
        latency_ms=250,
    )

    payload = error.to_trace_error()

    assert payload.type == "provider_error"
    assert secret not in payload.message
    assert "502" in payload.message

"""Tests for DeepSeekProvider — all HTTP calls mocked, no real network."""

from __future__ import annotations

import json
from unittest import mock

import httpx
import pytest
from pydantic import BaseModel, Field

from traceresearch.llm.deepseek_provider import DeepSeekProvider
from traceresearch.llm.provider import LLMProviderError


class _TestSchema(BaseModel):
    model_config = {"extra": "forbid"}
    value: str


class _TestSchemaWithList(BaseModel):
    items: list[str] = Field(min_length=1)


def _fake_response_json(content: str, prompt_tokens: int = 10, completion_tokens: int = 5) -> dict:
    """Build an OpenAI-compatible chat completion response dict."""
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def _make_provider(**overrides) -> DeepSeekProvider:
    kwargs = {
        "api_key": "sk-test-key",
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com",
        **overrides,
    }
    return DeepSeekProvider(**kwargs)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestDeepSeekProviderSuccess:
    def test_returns_parsed_schema_on_valid_response(self):
        provider = _make_provider()
        response_data = _fake_response_json('{"value": "hello from llm"}')
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_data

        with mock.patch.object(httpx.Client, "post", return_value=mock_response):
            result = provider.complete("say hello", _TestSchema)

        assert isinstance(result, _TestSchema)
        assert result.value == "hello from llm"

    def test_parses_list_schema(self):
        provider = _make_provider()
        response_data = _fake_response_json('{"items": ["a", "b", "c"]}')
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_data

        with mock.patch.object(httpx.Client, "post", return_value=mock_response):
            result = provider.complete("list things", _TestSchemaWithList)

        assert result.items == ["a", "b", "c"]

    def test_sends_system_prompt_when_provided(self):
        provider = _make_provider()
        response_data = _fake_response_json('{"value": "ok"}')
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_data

        with mock.patch.object(httpx.Client, "post") as mock_post:
            mock_post.return_value = mock_response
            provider.complete("hi", _TestSchema, system_prompt="Be helpful.")

        call_kwargs = mock_post.call_args.kwargs
        body = json.loads(call_kwargs["content"])
        messages = body["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "Be helpful."
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "hi"

    def test_no_system_prompt_when_none(self):
        provider = _make_provider()
        response_data = _fake_response_json('{"value": "ok"}')
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_data

        with mock.patch.object(httpx.Client, "post") as mock_post:
            mock_post.return_value = mock_response
            provider.complete("hi", _TestSchema)

        body = json.loads(mock_post.call_args.kwargs["content"])
        assert len(body["messages"]) == 1
        assert body["messages"][0]["role"] == "user"

    def test_returns_token_usage(self):
        """Verify caller can inspect token usage after call."""
        provider = _make_provider()
        response_data = _fake_response_json('{"value": "ok"}', prompt_tokens=20, completion_tokens=8)
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_data

        with mock.patch.object(httpx.Client, "post", return_value=mock_response):
            provider.complete("hello", _TestSchema)

        usage = provider.last_token_usage
        assert usage is not None
        assert usage.prompt_tokens == 20
        assert usage.completion_tokens == 8
        assert usage.total_tokens == 28


# ---------------------------------------------------------------------------
# Error / failure tests
# ---------------------------------------------------------------------------

class TestDeepSeekProviderErrors:
    def test_timeout_raises_provider_error(self):
        provider = _make_provider(timeout_seconds=0.01)

        def _raise_timeout(*args, **kwargs):
            raise httpx.TimeoutException("timed out")

        with mock.patch.object(httpx.Client, "post", side_effect=_raise_timeout):
            with pytest.raises(LLMProviderError) as exc_info:
                provider.complete("hi", _TestSchema)
            assert exc_info.value.reason == "timeout"

    def test_rate_limit_429_raises_provider_error(self):
        provider = _make_provider()
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": "rate limited"}

        with mock.patch.object(httpx.Client, "post", return_value=mock_response):
            with pytest.raises(LLMProviderError) as exc_info:
                provider.complete("hi", _TestSchema)
            assert exc_info.value.reason == "rate_limit"

    def test_http_500_raises_provider_error(self):
        provider = _make_provider()
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 500

        with mock.patch.object(httpx.Client, "post", return_value=mock_response):
            with pytest.raises(LLMProviderError) as exc_info:
                provider.complete("hi", _TestSchema)
            assert exc_info.value.reason == "provider_error"

    def test_http_400_raises_provider_error(self):
        provider = _make_provider()
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 400

        with mock.patch.object(httpx.Client, "post", return_value=mock_response):
            with pytest.raises(LLMProviderError) as exc_info:
                provider.complete("hi", _TestSchema)
            assert exc_info.value.reason == "provider_error"

    def test_invalid_json_response_raises(self):
        provider = _make_provider()
        response_data = _fake_response_json("not valid json for schema {")
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_data

        with mock.patch.object(httpx.Client, "post", return_value=mock_response):
            with pytest.raises(LLMProviderError) as exc_info:
                provider.complete("hi", _TestSchema)
            assert exc_info.value.reason == "invalid_response"

    def test_schema_validation_failure_raises(self):
        """LLM returns valid JSON but missing required field → invalid_response."""
        provider = _make_provider()
        # _TestSchema needs "value" but we return {}:
        response_data = _fake_response_json("{}")
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_data

        with mock.patch.object(httpx.Client, "post", return_value=mock_response):
            with pytest.raises(LLMProviderError) as exc_info:
                provider.complete("hi", _TestSchema)
            assert exc_info.value.reason == "invalid_response"

    def test_schema_extra_field_raises_if_forbid(self):
        """Pydantic extra=forbid → extra field triggers validation error."""
        provider = _make_provider()
        response_data = _fake_response_json('{"value": "ok", "extra_field": "nope"}')
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response_data

        with mock.patch.object(httpx.Client, "post", return_value=mock_response):
            with pytest.raises(LLMProviderError) as exc_info:
                provider.complete("hi", _TestSchema)
            assert exc_info.value.reason == "invalid_response"

    def test_missing_choices_in_response_raises(self):
        provider = _make_provider()
        mock_response = mock.Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"usage": {}}  # no "choices"

        with mock.patch.object(httpx.Client, "post", return_value=mock_response):
            with pytest.raises(LLMProviderError) as exc_info:
                provider.complete("hi", _TestSchema)
            assert exc_info.value.reason == "invalid_response"

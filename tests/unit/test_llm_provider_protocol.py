"""Tests for LLMProvider ABC and LLMProviderError."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from traceresearch.llm.provider import LLMProvider, LLMProviderError


class FakeSchema(BaseModel):
    value: str


class TestLLMProviderABC:
    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore[abstract]

    def test_concrete_subclass_needs_complete(self):
        with pytest.raises(TypeError):

            class Incomplete(LLMProvider):
                pass  # missing complete(), provider_name, model

            Incomplete()  # type: ignore[abstract]

    def test_concrete_subclass_needs_provider_name(self):
        with pytest.raises(TypeError):

            class MissingProviderName(LLMProvider):
                @property
                def model(self) -> str:
                    return "test"

                def complete(
                    self,
                    prompt: str,
                    response_schema: type[BaseModel],
                    system_prompt: str | None = None,
                ) -> BaseModel:
                    return response_schema(value="ok")

            MissingProviderName()  # type: ignore[abstract]

    def test_concrete_subclass_needs_model(self):
        with pytest.raises(TypeError):

            class MissingModel(LLMProvider):
                @property
                def provider_name(self) -> str:
                    return "test"

                def complete(
                    self,
                    prompt: str,
                    response_schema: type[BaseModel],
                    system_prompt: str | None = None,
                ) -> BaseModel:
                    return response_schema(value="ok")

            MissingModel()  # type: ignore[abstract]

    def test_valid_subclass_instantiates(self):
        class Valid(LLMProvider):
            @property
            def provider_name(self) -> str:
                return "test-prov"

            @property
            def model(self) -> str:
                return "test-model"

            def complete(
                self,
                prompt: str,
                response_schema: type[BaseModel],
                system_prompt: str | None = None,
            ) -> BaseModel:
                return response_schema(value="from-llm")

        instance = Valid()
        assert instance.provider_name == "test-prov"
        assert instance.model == "test-model"
        result = instance.complete("hello", FakeSchema)
        assert isinstance(result, FakeSchema)
        assert result.value == "from-llm"

    def test_complete_with_system_prompt(self):
        """system_prompt is Optional — verify it's passed through."""

        class WithSystemPrompt(LLMProvider):
            @property
            def provider_name(self) -> str:
                return "test"

            @property
            def model(self) -> str:
                return "test"

            def complete(
                self,
                prompt: str,
                response_schema: type[BaseModel],
                system_prompt: str | None = None,
            ) -> BaseModel:
                assert system_prompt == "You are helpful."
                return response_schema(value="ok")

        WithSystemPrompt().complete("hi", FakeSchema, system_prompt="You are helpful.")


class TestLLMProviderError:
    def test_error_contains_all_fields(self):
        err = LLMProviderError(
            reason="timeout",
            provider="deepseek",
            model="deepseek-chat",
            latency_ms=60.0,
        )
        assert err.reason == "timeout"
        assert err.provider == "deepseek"
        assert err.model == "deepseek-chat"
        assert err.latency_ms == 60.0
        assert "timeout" in str(err)
        assert "deepseek" in str(err)

    def test_error_with_invalid_response_reason(self):
        err = LLMProviderError(
            reason="invalid_response",
            provider="deepseek",
            model="deepseek-chat",
            latency_ms=1.5,
        )
        assert "invalid_response" in str(err)

    def test_error_with_rate_limit_reason(self):
        err = LLMProviderError(
            reason="rate_limit",
            provider="deepseek",
            model="deepseek-chat",
            latency_ms=0.2,
        )
        assert "rate_limit" in str(err)

    def test_error_with_provider_error_reason(self):
        err = LLMProviderError(
            reason="provider_error",
            provider="deepseek",
            model="deepseek-chat",
            latency_ms=2.0,
        )
        assert "provider_error" in str(err)

    def test_error_with_no_api_key_reason(self):
        err = LLMProviderError(
            reason="no_api_key",
            provider="deepseek",
            model="deepseek-chat",
            latency_ms=0.0,
        )
        assert "no_api_key" in str(err)

"""Tests for LLMProviderConfig — env-var reading and defaults."""

from __future__ import annotations

import os
from unittest import mock

from traceresearch.llm.config import LLMProviderConfig


class TestLLMProviderConfigFromEnv:
    def test_reads_project_env_vars(self):
        env = {
            "TRACERESEARCH_LLM_PROVIDER": "deepseek",
            "TRACERESEARCH_LLM_API_KEY": "sk-test-123",
            "TRACERESEARCH_LLM_MODEL": "deepseek-chat",
            "TRACERESEARCH_LLM_BASE_URL": "https://api.deepseek.com",
            "TRACERESEARCH_LLM_TIMEOUT": "30",
            "TRACERESEARCH_LLM_MAX_TOKENS": "2048",
            "TRACERESEARCH_LLM_TEMPERATURE": "0.3",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = LLMProviderConfig.from_env()
        assert cfg.provider == "deepseek"
        assert cfg.api_key == "sk-test-123"
        assert cfg.model == "deepseek-chat"
        assert cfg.base_url == "https://api.deepseek.com"
        assert cfg.timeout_seconds == 30.0
        assert cfg.max_tokens == 2048
        assert cfg.temperature == 0.3

    def test_defaults_when_no_env_vars(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = LLMProviderConfig.from_env()
        assert cfg.provider == "deepseek"
        assert cfg.api_key == ""
        assert cfg.model == "deepseek-chat"
        assert cfg.base_url == "https://api.deepseek.com"
        assert cfg.timeout_seconds == 60.0
        assert cfg.max_tokens == 4096
        assert cfg.temperature == 0.0

    def test_falls_back_to_deepseek_api_key(self):
        env = {"DEEPSEEK_API_KEY": "sk-deepseek-456"}
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = LLMProviderConfig.from_env()
        assert cfg.api_key == "sk-deepseek-456"

    def test_project_env_overrides_provider_specific(self):
        env = {
            "TRACERESEARCH_LLM_API_KEY": "sk-project-789",
            "DEEPSEEK_API_KEY": "sk-deepseek-000",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = LLMProviderConfig.from_env()
        assert cfg.api_key == "sk-project-789"

    def test_is_configured_false_when_no_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = LLMProviderConfig.from_env()
        assert cfg.is_configured() is False

    def test_is_configured_true_when_key_present(self):
        env = {"TRACERESEARCH_LLM_API_KEY": "sk-test"}
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = LLMProviderConfig.from_env()
        assert cfg.is_configured() is True

    def test_timeout_parsed_as_float(self):
        env = {"TRACERESEARCH_LLM_TIMEOUT": "90"}
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = LLMProviderConfig.from_env()
        assert isinstance(cfg.timeout_seconds, float)
        assert cfg.timeout_seconds == 90.0

    def test_invalid_timeout_raises(self):
        env = {"TRACERESEARCH_LLM_TIMEOUT": "not-a-number"}
        with mock.patch.dict(os.environ, env, clear=True):
            try:
                LLMProviderConfig.from_env()
            except ValueError:
                pass
            else:
                raise AssertionError("Expected ValueError for invalid timeout")

    def test_invalid_max_tokens_raises(self):
        env = {"TRACERESEARCH_LLM_MAX_TOKENS": "-5"}
        with mock.patch.dict(os.environ, env, clear=True):
            try:
                LLMProviderConfig.from_env()
            except ValueError:
                pass
            else:
                raise AssertionError("Expected ValueError for invalid max_tokens")

    def test_invalid_temperature_raises(self):
        env = {"TRACERESEARCH_LLM_TEMPERATURE": "not-a-number"}
        with mock.patch.dict(os.environ, env, clear=True):
            try:
                LLMProviderConfig.from_env()
            except ValueError:
                pass
            else:
                raise AssertionError("Expected ValueError for invalid temperature")

    def test_empty_api_key_does_not_raise(self):
        """No API key is NOT an error — it means 'not configured'."""
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = LLMProviderConfig.from_env()
        assert cfg.api_key == ""
        assert cfg.is_configured() is False

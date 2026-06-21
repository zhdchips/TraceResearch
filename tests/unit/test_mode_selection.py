"""Tests for mode_factory — Writer/Verifier mode selection logic."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from traceresearch.agents.llm_verifier import LLMVerifier
from traceresearch.agents.llm_writer import LLMWriter
from traceresearch.agents.verifier import Verifier
from traceresearch.agents.writer import Writer
from traceresearch.harness.mode_factory import (
    build_verifier,
    build_writer,
    resolve_mode,
)
from traceresearch.llm.provider import LLMProvider


class _FakeProvider(LLMProvider):
    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return "fake"

    def complete(self, prompt, response_schema, system_prompt=None):
        return response_schema()


# ---------------------------------------------------------------------------
# resolve_mode
# ---------------------------------------------------------------------------

class TestResolveMode:
    def test_explicit_llm_wins(self):
        assert resolve_mode("llm", "WRITER", default="deterministic") == "llm"

    def test_explicit_deterministic_wins(self):
        assert resolve_mode("deterministic", "WRITER", default="deterministic") == "deterministic"

    def test_default_returns_deterministic(self):
        assert resolve_mode("deterministic", "WRITER", default="deterministic") == "deterministic"

    def test_unknown_mode_defaults_to_deterministic(self):
        assert resolve_mode("bogus", "WRITER", default="deterministic") == "deterministic"


# ---------------------------------------------------------------------------
# build_writer
# ---------------------------------------------------------------------------


class TestBuildWriter:
    def test_deterministic_mode_returns_writer(self):
        w = build_writer(mode="deterministic", llm_provider=None)
        assert isinstance(w, Writer)

    def test_llm_mode_with_provider_returns_llm_writer(self):
        w = build_writer(mode="llm", llm_provider=_FakeProvider())
        assert isinstance(w, LLMWriter)

    def test_llm_mode_without_provider_raises(self):
        with pytest.raises(ValueError, match="LLM provider"):
            build_writer(mode="llm", llm_provider=None)

    def test_unknown_mode_returns_deterministic(self):
        w = build_writer(mode="bogus", llm_provider=_FakeProvider())
        assert isinstance(w, Writer)


# ---------------------------------------------------------------------------
# build_verifier
# ---------------------------------------------------------------------------


class TestBuildVerifier:
    def test_deterministic_mode_returns_verifier(self):
        v = build_verifier(mode="deterministic", llm_provider=None)
        assert isinstance(v, Verifier)

    def test_llm_mode_with_provider_returns_llm_verifier(self):
        v = build_verifier(mode="llm", llm_provider=_FakeProvider())
        assert isinstance(v, LLMVerifier)

    def test_llm_mode_without_provider_raises(self):
        with pytest.raises(ValueError, match="LLM provider"):
            build_verifier(mode="llm", llm_provider=None)

    def test_unknown_mode_returns_deterministic(self):
        v = build_verifier(mode="bogus", llm_provider=_FakeProvider())
        assert isinstance(v, Verifier)

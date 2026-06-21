"""Factory functions for Writer/Verifier mode selection."""

from __future__ import annotations

import os

from traceresearch.agents.llm_verifier import LLMVerifier
from traceresearch.agents.llm_writer import LLMWriter
from traceresearch.agents.verifier import Verifier
from traceresearch.agents.verifier_protocol import VerifierProtocol
from traceresearch.agents.writer import Writer
from traceresearch.agents.writer_protocol import WriterProtocol
from traceresearch.llm.provider import LLMProvider

VALID_MODES = ("deterministic", "llm")


def resolve_mode(
    explicit_mode: str | None,
    component: str,
    default: str = "deterministic",
    _env: dict[str, str] | None = None,
) -> str:
    """Resolve the effective mode for a Writer or Verifier component.

    Priority: explicit_mode > env var > default.
    """
    env = _env if _env is not None else os.environ
    if explicit_mode and explicit_mode != default:
        if explicit_mode in VALID_MODES:
            return explicit_mode
        return default  # unknown mode → default

    if explicit_mode == "llm":
        return "llm"

    env_var = f"TRACERESEARCH_{component.upper()}_MODE"
    env_value = env.get(env_var, "")
    if env_value in VALID_MODES:
        return env_value

    return default


def build_writer(
    *,
    mode: str,
    llm_provider: LLMProvider | None,
) -> WriterProtocol:
    """Build a WriterProtocol instance based on mode."""
    if mode == "llm":
        if llm_provider is None:
            raise ValueError(
                "LLM provider is required when writer mode is 'llm'. "
                "Set TRACERESEARCH_LLM_API_KEY or provide a provider instance."
            )
        return LLMWriter(llm_provider)
    return Writer()


def build_verifier(
    *,
    mode: str,
    llm_provider: LLMProvider | None,
) -> VerifierProtocol:
    """Build a VerifierProtocol instance based on mode."""
    if mode == "llm":
        if llm_provider is None:
            raise ValueError(
                "LLM provider is required when verifier mode is 'llm'. "
                "Set TRACERESEARCH_LLM_API_KEY or provide a provider instance."
            )
        return LLMVerifier(llm_provider)
    return Verifier()

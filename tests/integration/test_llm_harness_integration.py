"""Integration tests for Harness with LLM Writer/Verifier modes — mock LLMProvider."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from pydantic import BaseModel

from traceresearch.harness.orchestrator import ResearchHarness
from traceresearch.llm.provider import LLMProvider, LLMProviderError
from traceresearch.llm.schemas import (
    LLMClaimJudgmentSchema,
    LLMFinalReportSchema,
    LLMFindingSchema,
    LLMVerificationResultSchema,
)
from traceresearch.source_discovery.fixture_provider import FixtureSourceProvider


# ---------------------------------------------------------------------------
# Mock LLM Provider — returns pre-built schemas
# ---------------------------------------------------------------------------


class _IntegrationFakeProvider(LLMProvider):
    """Returns valid LLM responses for integration tests."""

    def __init__(self) -> None:
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return "integration-fake"

    @property
    def model(self) -> str:
        return "fake-model"

    def complete(
        self,
        prompt: str,
        response_schema: type[BaseModel],
        system_prompt: str | None = None,
    ) -> BaseModel:
        self.call_count += 1
        if response_schema is LLMFinalReportSchema:
            return LLMFinalReportSchema(
                executive_summary="Integration test summary.",
                findings=[
                    LLMFindingSchema(
                        text="Integration finding with evidence.",
                        evidence_ids=["EVID-001"],
                        confidence="high",
                    )
                ],
                limitations=["Integration test limitation."],
                evidence_references=["EVID-001: Integration Source"],
                follow_up_questions=["Integration follow-up?"],
            )
        if response_schema is LLMVerificationResultSchema:
            return LLMVerificationResultSchema(
                claim_results=[
                    LLMClaimJudgmentSchema(
                        claim_id="CL-test-case001-001",
                        support_status="supported",
                        reasoning="Integration evidence supports claim.",
                    )
                ],
                overall_notes=["Integration verification complete."],
            )
        raise RuntimeError(f"Unexpected schema: {response_schema}")


class _IntegrationFailingProvider(LLMProvider):
    """Always fails — triggers fallback."""

    @property
    def provider_name(self) -> str:
        return "failing"

    @property
    def model(self) -> str:
        return "failing-model"

    def complete(
        self,
        prompt: str,
        response_schema: type[BaseModel],
        system_prompt: str | None = None,
    ) -> BaseModel:
        raise LLMProviderError("timeout", "failing", "failing-model", 5000)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHarnessDefaultDeterministic:
    """Default mode (deterministic) MUST behave exactly as before."""

    def test_default_run_fixture_produces_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = ResearchHarness().run_fixture(
                query="Test query for default mode.",
                case_id="001-framework-comparison",
                output_dir=tmp,
            )
            assert result.status.value == "completed"
            assert result.final_report_path is not None
            report = Path(result.final_report_path).read_text()
            assert "Executive Summary" in report


class TestHarnessLLMWriterMode:
    """LLM Writer mode — uses LLMWriter with mock provider."""

    def test_llm_writer_mode_completes_run(self):
        provider = _IntegrationFakeProvider()
        with tempfile.TemporaryDirectory() as tmp:
            harness = ResearchHarness(
                writer_mode="llm",
                llm_provider=provider,
            )
            result = harness.run_fixture(
                query="Test query for LLM Writer.",
                case_id="001-framework-comparison",
                output_dir=tmp,
            )
            assert result.status.value == "completed"
            assert result.final_report_path is not None

    def test_llm_writer_run_creates_report_with_standard_sections(self):
        provider = _IntegrationFakeProvider()
        with tempfile.TemporaryDirectory() as tmp:
            harness = ResearchHarness(
                writer_mode="llm",
                llm_provider=provider,
            )
            result = harness.run_fixture(
                query="Test query for LLM Writer output.",
                case_id="001-framework-comparison",
                output_dir=tmp,
            )
            report = Path(result.final_report_path).read_text()
            assert "Executive Summary" in report
            assert "Findings" in report
            assert result.final_report_path is not None


class TestHarnessLLMVerifierMode:
    """LLM Verifier mode — uses LLMVerifier with mock provider."""

    def test_llm_verifier_mode_completes_run(self):
        provider = _IntegrationFakeProvider()
        with tempfile.TemporaryDirectory() as tmp:
            harness = ResearchHarness(
                verifier_mode="llm",
                llm_provider=provider,
            )
            result = harness.run_fixture(
                query="Test query for LLM Verifier.",
                case_id="001-framework-comparison",
                output_dir=tmp,
            )
            assert result.status.value == "completed"


class TestHarnessBothLLMModes:
    """Both Writer + Verifier in LLM mode."""

    def test_both_llm_modes_complete(self):
        provider = _IntegrationFakeProvider()
        with tempfile.TemporaryDirectory() as tmp:
            harness = ResearchHarness(
                writer_mode="llm",
                verifier_mode="llm",
                llm_provider=provider,
            )
            result = harness.run_fixture(
                query="Both LLM modes.",
                case_id="001-framework-comparison",
                output_dir=tmp,
            )
            assert result.status.value == "completed"
            assert result.final_report_path is not None
            report = Path(result.final_report_path).read_text()
            assert "Executive Summary" in report


class TestHarnessLLMFallback:
    """LLM failure → deterministic fallback → run still completes."""

    def test_writer_fallback_completes_run(self):
        provider = _IntegrationFailingProvider()
        with tempfile.TemporaryDirectory() as tmp:
            harness = ResearchHarness(
                writer_mode="llm",
                llm_provider=provider,
            )
            result = harness.run_fixture(
                query="Writer fallback test.",
                case_id="001-framework-comparison",
                output_dir=tmp,
            )
            assert result.status.value == "completed"
            report = Path(result.final_report_path).read_text()
            assert "Executive Summary" in report

    def test_verifier_fallback_completes_run(self):
        provider = _IntegrationFailingProvider()
        with tempfile.TemporaryDirectory() as tmp:
            harness = ResearchHarness(
                verifier_mode="llm",
                llm_provider=provider,
            )
            result = harness.run_fixture(
                query="Verifier fallback test.",
                case_id="001-framework-comparison",
                output_dir=tmp,
            )
            assert result.status.value == "completed"

    def test_both_fallback_completes_run(self):
        provider = _IntegrationFailingProvider()
        with tempfile.TemporaryDirectory() as tmp:
            harness = ResearchHarness(
                writer_mode="llm",
                verifier_mode="llm",
                llm_provider=provider,
            )
            result = harness.run_fixture(
                query="Both fallback test.",
                case_id="001-framework-comparison",
                output_dir=tmp,
            )
            assert result.status.value == "completed"


class TestHarnessDirectInjection:
    """writer=/verifier= kwargs take priority over mode-based construction."""

    def test_direct_writer_overrides_mode(self):
        provider = _IntegrationFakeProvider()
        from traceresearch.agents.writer import Writer

        direct = Writer()
        with tempfile.TemporaryDirectory() as tmp:
            harness = ResearchHarness(
                writer=direct,  # explicit inject
                writer_mode="llm",  # should be ignored
                llm_provider=provider,
            )
            result = harness.run_fixture(
                query="Direct injection test.",
                case_id="001-framework-comparison",
                output_dir=tmp,
            )
            assert result.status.value == "completed"
            report = Path(result.final_report_path).read_text()
            # Deterministic Writer output, not LLM output
            assert "Integration test summary" not in report
            assert "Executive Summary" in report

    def test_direct_verifier_overrides_mode(self):
        provider = _IntegrationFakeProvider()
        from traceresearch.agents.verifier import Verifier

        direct = Verifier()
        with tempfile.TemporaryDirectory() as tmp:
            harness = ResearchHarness(
                verifier=direct,
                verifier_mode="llm",
                llm_provider=provider,
            )
            result = harness.run_fixture(
                query="Direct verifier test.",
                case_id="001-framework-comparison",
                output_dir=tmp,
            )
            assert result.status.value == "completed"

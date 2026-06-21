"""Real LLM smoke tests — manual only, requires DEEPSEEK_API_KEY.

Run: python3 -m pytest tests/llm_smoke/ -m llm_smoke -v
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from dotenv import load_dotenv

from traceresearch.harness.orchestrator import ResearchHarness
from traceresearch.llm.config import LLMProviderConfig
from traceresearch.llm.deepseek_provider import DeepSeekProvider

load_dotenv()

# Skip if no API key
_CFG = LLMProviderConfig.from_env()
if not _CFG.is_configured():
    pytest.skip("No LLM API key configured — set DEEPSEEK_API_KEY", allow_module_level=True)


def _make_provider():
    return DeepSeekProvider(
        api_key=_CFG.api_key,
        model=_CFG.model,
        base_url=_CFG.base_url,
        timeout_seconds=_CFG.timeout_seconds,
        max_tokens=_CFG.max_tokens,
        temperature=_CFG.temperature,
    )


@pytest.mark.llm_smoke
class TestRealLLMWriterSmoke:
    """Real LLM Writer smoke — uses DeepSeek API."""

    def test_writer_generates_report_with_evidence_ids(self):
        provider = _make_provider()
        with tempfile.TemporaryDirectory() as tmp:
            harness = ResearchHarness(
                writer_mode="llm",
                llm_provider=provider,
            )
            result = harness.run_fixture(
                query="Compare FastAPI, Django-Ninja, and Flask for building REST APIs.",
                case_id="001-framework-comparison",
                output_dir=tmp,
            )
            assert result.status.value == "completed"
            report = Path(result.final_report_path).read_text()
            assert "Executive Summary" in report
            assert "Findings" in report
            # Must have evidence references
            assert "EV-" in report or "EVID-" in report

    def test_writer_final_report_has_standard_sections(self):
        provider = _make_provider()
        with tempfile.TemporaryDirectory() as tmp:
            harness = ResearchHarness(
                writer_mode="llm",
                llm_provider=provider,
            )
            result = harness.run_fixture(
                query="Test LLM Writer sections.",
                case_id="001-framework-comparison",
                output_dir=tmp,
            )
            report = Path(result.final_report_path).read_text()
            for section in ["Executive Summary", "Findings", "Limitations", "Follow-up"]:
                assert section in report, f"Missing section: {section}"


@pytest.mark.llm_smoke
class TestRealLLMVerifierSmoke:
    """Real LLM Verifier smoke — uses DeepSeek API."""

    def test_verifier_completes_run_with_llm_mode(self):
        provider = _make_provider()
        with tempfile.TemporaryDirectory() as tmp:
            harness = ResearchHarness(
                verifier_mode="llm",
                llm_provider=provider,
            )
            result = harness.run_fixture(
                query="Test LLM Verifier.",
                case_id="001-framework-comparison",
                output_dir=tmp,
            )
            assert result.status.value == "completed"


@pytest.mark.llm_smoke
class TestRealLLMBothModesSmoke:
    """Both Writer + Verifier LLM smoke — uses DeepSeek API."""

    def test_both_llm_modes_produce_complete_run(self):
        provider = _make_provider()
        with tempfile.TemporaryDirectory() as tmp:
            harness = ResearchHarness(
                writer_mode="llm",
                verifier_mode="llm",
                llm_provider=provider,
            )
            result = harness.run_fixture(
                query="Full LLM smoke test — both modes.",
                case_id="001-framework-comparison",
                output_dir=tmp,
            )
            assert result.status.value == "completed"
            assert result.final_report_path is not None
            report = Path(result.final_report_path).read_text()
            assert len(report) > 200  # non-trivial output

    def test_trace_records_llm_fields(self):
        provider = _make_provider()
        with tempfile.TemporaryDirectory() as tmp:
            harness = ResearchHarness(
                writer_mode="llm",
                verifier_mode="llm",
                llm_provider=provider,
            )
            result = harness.run_fixture(
                query="Trace LLM fields test.",
                case_id="001-framework-comparison",
                output_dir=tmp,
            )
            trace_path = Path(result.artifact_dir) / "trace.jsonl"
            trace_lines = trace_path.read_text().splitlines()
            llm_events = [l for l in trace_lines if '"llm_mode":"llm"' in l]
            assert len(llm_events) >= 2, f"Expected >=2 LLM trace events, got {len(llm_events)}"
            # At least one should have llm_model
            assert any('"llm_model":"deepseek-chat"' in e for e in llm_events)

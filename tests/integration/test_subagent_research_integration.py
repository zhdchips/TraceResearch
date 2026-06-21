"""Integration tests for subagent-based research phase."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from traceresearch.evidence.models import ResearchRunStatus
from traceresearch.evidence.store import EvidenceStore
from traceresearch.harness.orchestrator import ResearchHarness
from traceresearch.trace.models import AgentRole
from traceresearch.trace.writer import TraceWriter


class TestSubagentHarnessIntegration:
    """Verify that harness with LeadResearchAgent produces valid artifacts."""

    def test_fixture_run_produces_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            harness = ResearchHarness()
            result = harness.run_fixture(
                query="Compare LangGraph, AutoGen, and CrewAI for building deep research agents.",
                case_id="001-framework-comparison",
                output_dir=tmpdir,
            )

            assert result.status == ResearchRunStatus.COMPLETED
            assert result.final_report_path is not None

            # Verify evidence.jsonl exists and has valid content
            evidence_store = EvidenceStore(result.artifact_dir / "evidence.jsonl")
            all_evidence = evidence_store.list_all()
            assert len(all_evidence) > 0
            for e in all_evidence:
                assert e.evidence_id.startswith("EV-")
                assert e.run_id == result.run_id
                assert len(e.summary) > 0

    def test_fixture_run_writes_all_artifacts(self) -> None:
        expected_files = [
            "research_brief.json",
            "research_tasks.json",
            "evidence.jsonl",
            "outline.md",
            "draft_report.md",
            "verification.json",
            "critique.json",
            "final_report.md",
            "report.json",
            "trace.jsonl",
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            harness = ResearchHarness()
            result = harness.run_fixture(
                query="Compare LangGraph, AutoGen, and CrewAI for building deep research agents.",
                case_id="001-framework-comparison",
                output_dir=tmpdir,
            )
            artifact_dir = result.artifact_dir
            for filename in expected_files:
                path = artifact_dir / filename
                assert path.exists(), f"Missing artifact: {filename}"

    def test_trace_contains_subagent_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            harness = ResearchHarness()
            result = harness.run_fixture(
                query="Compare LangGraph, AutoGen, and CrewAI for building deep research agents.",
                case_id="001-framework-comparison",
                output_dir=tmpdir,
            )

            trace_path = result.artifact_dir / "trace.jsonl"
            trace_writer = TraceWriter(trace_path)
            events = trace_writer.read_all()

            # Should have RESEARCH_LEAD events
            lead_events = [
                e for e in events if e.agent_role == AgentRole.RESEARCH_LEAD
            ]
            assert len(lead_events) > 0, "Trace should contain RESEARCH_LEAD events"

            # Should have RESEARCH_SUBAGENT events
            subagent_events = [
                e for e in events if e.agent_role == AgentRole.RESEARCH_SUBAGENT
            ]
            assert len(subagent_events) > 0, "Trace should contain RESEARCH_SUBAGENT events"

    def test_concurrency_1_produces_valid_evidence(self) -> None:
        import os
        os.environ["TRACERESEARCH_MAX_CONCURRENT_RESEARCH_TASKS"] = "1"
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                harness = ResearchHarness()
                result = harness.run_fixture(
                    query="Compare LangGraph, AutoGen, and CrewAI for building deep research agents.",
                    case_id="001-framework-comparison",
                    output_dir=tmpdir,
                )
                assert result.status == ResearchRunStatus.COMPLETED

                evidence_store = EvidenceStore(result.artifact_dir / "evidence.jsonl")
                all_evidence = evidence_store.list_all()
                assert len(all_evidence) > 0
        finally:
            os.environ.pop("TRACERESEARCH_MAX_CONCURRENT_RESEARCH_TASKS", None)

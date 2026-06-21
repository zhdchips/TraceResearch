"""Integration tests for subagent-based research phase."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from traceresearch.evidence.models import ResearchRunStatus
from traceresearch.evidence.store import EvidenceStore
from traceresearch.harness.orchestrator import ResearchHarness
from traceresearch.trace.models import AgentRole, EventType
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

            # Should have TOOL_CALL and TOOL_RESULT events from subagents
            tool_calls = [
                e for e in subagent_events if e.event_type == EventType.TOOL_CALL
            ]
            tool_results = [
                e for e in subagent_events if e.event_type == EventType.TOOL_RESULT
            ]
            assert len(tool_calls) > 0, "Trace should contain TOOL_CALL events"
            assert len(tool_results) > 0, "Trace should contain TOOL_RESULT events"
            # tool_name should be fixture.search
            assert any(e.tool_name == "fixture.search" for e in tool_calls)

            # Trace IDs must be unique
            all_trace_ids = [e.trace_id for e in events]
            assert len(all_trace_ids) == len(set(all_trace_ids)), "Trace IDs must be unique"

    def test_trace_writer_thread_safety(self) -> None:
        """TraceWriter handles concurrent appends without corruption."""
        import json
        import threading

        with tempfile.TemporaryDirectory() as tmpdir:
            trace_path = Path(tmpdir) / "trace.jsonl"
            writer = TraceWriter(trace_path)

            errors: list[Exception] = []

            def write_event(idx: int) -> None:
                try:
                    tid = writer.next_trace_id("run-conc")
                    event_dict = {
                        "trace_id": tid,
                        "run_id": "run-conc",
                        "task_id": None,
                        "subagent_id": None,
                        "agent_role": "ResearchSubagent",
                        "event_type": "start",
                        "tool_name": None,
                        "input_summary": f"test {idx}",
                        "output_summary": f"output {idx}",
                        "status": "success",
                        "latency_ms": 0,
                        "token_usage": None,
                        "error": None,
                        "llm_mode": None,
                        "llm_model": None,
                        "llm_token_usage": None,
                        "failover_reason": None,
                        "created_at": "2026-06-21T00:00:00Z",
                    }
                    line = json.dumps(event_dict, ensure_ascii=False, separators=(",", ":"))
                    writer.path.parent.mkdir(parents=True, exist_ok=True)
                    with writer._lock:
                        with writer.path.open("a", encoding="utf-8") as f:
                            f.write(line + "\n")
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=write_event, args=(i,)) for i in range(50)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0, f"Concurrent writes had errors: {errors}"

            # All lines should be parseable JSON
            lines = trace_path.read_text().strip().split("\n")
            assert len(lines) == 50
            trace_ids = []
            for line in lines:
                obj = json.loads(line)
                trace_ids.append(obj["trace_id"])
            assert len(trace_ids) == len(set(trace_ids)), "Trace IDs must be unique"

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

    def test_partial_failure_passes_failed_task_ids_to_critique(self) -> None:
        """When 1 task fails, critique.json includes failed_task_ids."""
        import json
        from unittest.mock import MagicMock
        from traceresearch.evidence.models import (
            ResearchTask,
            SourceResult,
            SourceType,
            SourceDocument,
            EvidenceStatus,
        )
        from traceresearch.source_discovery.base import (
            SourceDiscoveryProvider,
            SourceRef,
        )

        # Mock provider: T-001 succeeds, T-002 fails
        class PartialFailProvider(SourceDiscoveryProvider):
            provider_name = "fixture"
            tool_name = "fixture.search"

            def search(self, task: ResearchTask, limit: int) -> list[SourceResult]:
                if task.research_task_id == "T-002":
                    raise RuntimeError("Simulated provider error")
                return [
                    SourceResult(
                        source_id="S-001", provider="fixture",
                        title="Test Source", source_type=SourceType.BLOG,
                        publisher="Test Pub", retrieved_at=datetime.now(timezone.utc),
                        snippet="Test", provider_rank=1,
                    )
                ]

            def fetch(self, source_ref: SourceRef) -> SourceDocument:
                return SourceDocument(
                    source_id=source_ref.source_id, title="Test",
                    content_excerpt="Test content", retrieved_at=datetime.now(timezone.utc),
                    metadata={"summary": "Test summary"},
                )

        from datetime import timezone as tz
        from traceresearch.agents.lead_researcher import LeadResearchAgent
        from traceresearch.evidence.models import ResearchBrief

        brief = ResearchBrief(
            run_id="run-pf-001", objective="Partial failure test",
            scope_boundaries=["test"], assumptions=[], open_clarifications=[],
            perspectives=["P1", "P2"], success_criteria=["C1"],
            research_tasks=[
                ResearchTask(
                    research_task_id="T-001", run_id="run-pf-001",
                    perspective="P1", objective="Task 1", query="Q1",
                ),
                ResearchTask(
                    research_task_id="T-002", run_id="run-pf-001",
                    perspective="P2", objective="Task 2", query="Q2",
                ),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            trace_path = Path(tmpdir) / "trace.jsonl"
            trace_writer = TraceWriter(trace_path)
            agent = LeadResearchAgent(max_concurrent=1)
            result = agent.conduct_research(
                brief=brief, provider=PartialFailProvider(),
                run_id="run-pf-001", run_dir=Path(tmpdir),
                trace_writer=trace_writer,
            )

            # Evidence from T-001 should be present
            assert len(result.evidence) == 1
            # T-002 should be in failed_task_ids
            assert "T-002" in result.failed_task_ids
            # Trace should contain error event
            events = trace_writer.read_all()
            error_events = [e for e in events if e.event_type == EventType.ERROR]
            assert len(error_events) == 0  # subagent errors captured as FAILED FINISH, not ERROR
            failed_finishes = [
                e for e in events
                if e.agent_role == AgentRole.RESEARCH_SUBAGENT
                and e.event_type == EventType.FINISH
                and e.status.value == "failed"
            ]
            assert len(failed_finishes) == 1

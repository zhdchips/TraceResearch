"""Integration tests for LeadAgentRuntime — full pipeline, trace chain, 004 regression."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone

import pytest

from traceresearch.evidence.models import (
    EvidenceStatus,
    ResearchRunStatus,
    SourceResult,
    SourceType,
)
from traceresearch.evidence.store import EvidenceStore
from traceresearch.harness.orchestrator import ResearchHarness
from traceresearch.trace.models import AgentRole, EventType
from traceresearch.trace.writer import TraceWriter


class TestLeadRuntimeFullPipeline:
    """Verify that the harness + runtime pipeline produces correct results."""

    def test_fixture_run_produces_evidence_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            harness = ResearchHarness()
            result = harness.run_fixture(
                query="Compare LangGraph, AutoGen, and CrewAI for building deep research agents.",
                case_id="001-framework-comparison",
                output_dir=tmpdir,
            )

            assert result.status == ResearchRunStatus.COMPLETED
            assert result.final_report_path is not None

            # Evidence should be produced
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

    def test_all_five_cases_pass(self) -> None:
        """All 5 eval cases should produce COMPLETED runs."""
        case_ids = [
            "001-framework-comparison",
            "002-financial-grounding",
            "003-ai-coding-agent-trends",
            "004-openhands-runtime",
            "005-rag-2026",
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            for case_id in case_ids:
                harness = ResearchHarness()
                result = harness.run_fixture(
                    query=f"Test query for {case_id}",
                    case_id=case_id,
                    output_dir=tmpdir,
                )
                assert result.status == ResearchRunStatus.COMPLETED, \
                    f"Case {case_id} failed with status {result.status}"


class TestTraceChain:
    """Verify that the trace contains the full execution chain with LEAD_RUNTIME events."""

    def test_trace_contains_lead_runtime_events(self) -> None:
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

            # Should have LEAD_RUNTIME events
            lead_runtime_events = [
                e for e in events if e.agent_role == AgentRole.LEAD_RUNTIME
            ]
            assert len(lead_runtime_events) > 0, \
                "Trace should contain LEAD_RUNTIME events"

            # Each step should have START, TOOL_CALL, TOOL_RESULT, FINISH
            step_names = {e.tool_name for e in lead_runtime_events}
            expected_steps = {
                "plan_research", "run_research_subagents", "write_report",
                "verify_report", "critique_report", "finalize_run",
            }
            for step in expected_steps:
                assert step in step_names, f"Missing step '{step}' in trace"

            # Verify event types for each step
            for step_name in expected_steps:
                step_events = [e for e in lead_runtime_events if e.tool_name == step_name]
                event_types = {e.event_type for e in step_events}
                assert EventType.START in event_types, f"Step {step_name} missing START"
                assert EventType.FINISH in event_types, f"Step {step_name} missing FINISH"
                # TOOL_CALL and TOOL_RESULT should be present
                assert EventType.TOOL_CALL in event_types, f"Step {step_name} missing TOOL_CALL"
                assert EventType.TOOL_RESULT in event_types, f"Step {step_name} missing TOOL_RESULT"

    def test_trace_shows_full_execution_chain(self) -> None:
        """Trace must show: LeadRuntime -> Planner -> ResearchLead -> ResearchSubagent -> Writer -> Verifier -> Critic"""
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

            # All expected agent roles should appear
            agent_roles = {e.agent_role for e in events}
            expected_roles = {
                AgentRole.LEAD_RUNTIME,
                AgentRole.PLANNER,
                AgentRole.RESEARCH_LEAD,
                AgentRole.RESEARCH_SUBAGENT,
                AgentRole.WRITER,
                AgentRole.VERIFIER,
                AgentRole.CRITIC,
                AgentRole.HARNESS,
            }
            for role in expected_roles:
                assert role in agent_roles, f"Missing agent role '{role}' in trace"

    def test_trace_ids_are_unique(self) -> None:
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

            all_trace_ids = [e.trace_id for e in events]
            assert len(all_trace_ids) == len(set(all_trace_ids)), \
                "All trace IDs must be unique"


class Test004Regression:
    """Verify that 004 research subagent features are preserved."""

    def test_subagent_trace_events_preserved(self) -> None:
        """RESEARCH_LEAD and RESEARCH_SUBAGENT events must still be present."""
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

            # RESEARCH_LEAD events
            lead_events = [e for e in events if e.agent_role == AgentRole.RESEARCH_LEAD]
            assert len(lead_events) > 0, "RESEARCH_LEAD events must be present"

            # RESEARCH_SUBAGENT events
            subagent_events = [e for e in events if e.agent_role == AgentRole.RESEARCH_SUBAGENT]
            assert len(subagent_events) > 0, "RESEARCH_SUBAGENT events must be present"

            # TOOL_CALL and TOOL_RESULT from subagents
            tool_calls = [
                e for e in subagent_events if e.event_type == EventType.TOOL_CALL
            ]
            tool_results = [
                e for e in subagent_events if e.event_type == EventType.TOOL_RESULT
            ]
            assert len(tool_calls) > 0, "Subagent TOOL_CALL events must be present"
            assert len(tool_results) > 0, "Subagent TOOL_RESULT events must be present"

    def test_evidence_ids_stable(self) -> None:
        """Evidence IDs should follow the EV-{run_id}-{seq:03d} pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            harness = ResearchHarness()
            result = harness.run_fixture(
                query="Compare LangGraph, AutoGen, and CrewAI for building deep research agents.",
                case_id="001-framework-comparison",
                output_dir=tmpdir,
            )

            evidence_store = EvidenceStore(result.artifact_dir / "evidence.jsonl")
            all_evidence = evidence_store.list_all()
            for e in all_evidence:
                assert e.evidence_id.startswith(f"EV-{result.run_id}-"), \
                    f"Evidence ID {e.evidence_id} does not match expected pattern"

    def test_partial_failure_passes_failed_task_ids_to_critique(self) -> None:
        """From 004: when 1 task fails, critique includes failed_task_ids."""
        import json
        from traceresearch.agents.lead_researcher import LeadResearchAgent
        from traceresearch.evidence.models import (
            ResearchBrief,
            ResearchTask,
            SourceDocument,
        )
        from traceresearch.source_discovery.base import (
            SourceDiscoveryProvider,
            SourceRef,
        )

        class PartialFailProvider(SourceDiscoveryProvider):
            provider_name = "fixture"
            tool_name = "fixture.search"

            def search(self, task, limit):
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

            def fetch(self, source_ref):
                return SourceDocument(
                    source_id=source_ref.source_id, title="Test",
                    content_excerpt="Test content", retrieved_at=datetime.now(timezone.utc),
                    metadata={"summary": "Test summary"},
                )

        brief = ResearchBrief(
            run_id="run-pf-002", objective="Partial failure test",
            scope_boundaries=["test"], assumptions=[], open_clarifications=[],
            perspectives=["P1", "P2"], success_criteria=["C1"],
            research_tasks=[
                ResearchTask(research_task_id="T-001", run_id="run-pf-002",
                             perspective="P1", objective="Task 1", query="Q1"),
                ResearchTask(research_task_id="T-002", run_id="run-pf-002",
                             perspective="P2", objective="Task 2", query="Q2"),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            from pathlib import Path
            trace_path = Path(tmpdir) / "trace.jsonl"
            trace_writer = TraceWriter(trace_path)
            agent = LeadResearchAgent(max_concurrent=1)
            result = agent.conduct_research(
                brief=brief, provider=PartialFailProvider(),
                run_id="run-pf-002", run_dir=Path(tmpdir),
                trace_writer=trace_writer,
            )

            # Evidence from T-001 should be present
            assert len(result.evidence) == 1
            # T-002 should be in failed_task_ids
            assert "T-002" in result.failed_task_ids

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


class TestCLIContract:
    """CLI contract: no new required parameters."""

    def test_harness_constructor_defaults_unchanged(self) -> None:
        """ResearchHarness() with no args should work."""
        harness = ResearchHarness()
        assert harness.planner is not None
        assert harness.lead_researcher is not None
        assert harness.writer is not None
        assert harness.verifier is not None
        assert harness.critic is not None

    def test_run_fixture_signature_unchanged(self) -> None:
        """run_fixture(query, case_id, output_dir) signature unchanged."""
        import inspect
        sig = inspect.signature(ResearchHarness.run_fixture)
        param_names = list(sig.parameters.keys())
        assert "query" in param_names
        assert "case_id" in param_names
        assert "output_dir" in param_names
        # No new unexpected required params (query/case_id/output_dir are original)
        required = [n for n, p in sig.parameters.items() if p.default is inspect.Parameter.empty]
        expected_required = {"self", "query", "case_id", "output_dir"}
        assert set(required) == expected_required, \
            f"Unexpected required params: {required}, expected: {expected_required}"

"""Tests for LeadResearchAgent."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from traceresearch.agents.lead_researcher import LeadResearchAgent
from traceresearch.agents.subagent_models import SubagentStatus
from traceresearch.evidence.models import (
    Evidence,
    EvidenceStatus,
    ResearchBrief,
    ResearchTask,
    SourceResult,
    SourceType,
)
from traceresearch.evidence.store import dedupe_key
from traceresearch.source_discovery.fixture_provider import FixtureSourceProvider
from traceresearch.trace.models import AgentRole, EventType
from traceresearch.trace.writer import TraceWriter

# Fixture case 001-framework-comparison has perspectives:
#   orchestration model, multi-agent collaboration, production readiness, risks and limitations
FIXTURE_CASE = "001-framework-comparison"
FIXTURE_PERSPECTIVES = [
    "orchestration model",
    "multi-agent collaboration",
    "production readiness",
]


def _make_brief(
    run_id: str = "run-001",
    tasks: list[ResearchTask] | None = None,
) -> ResearchBrief:
    if tasks is None:
        tasks = [
            ResearchTask(
                research_task_id="T-001",
                run_id=run_id,
                perspective="orchestration model",
                objective="Study architecture",
                query="How do frameworks handle orchestration?",
            ),
            ResearchTask(
                research_task_id="T-002",
                run_id=run_id,
                perspective="production readiness",
                objective="Study production readiness",
                query="What is the production readiness of these frameworks?",
            ),
        ]
    return ResearchBrief(
        run_id=run_id,
        objective="Test research",
        scope_boundaries=["test"],
        assumptions=[],
        open_clarifications=[],
        perspectives=FIXTURE_PERSPECTIVES,
        success_criteria=["All perspectives covered"],
        research_tasks=tasks,
    )


def _make_evidence(
    evidence_id: str = "EV-run-001-001",
    run_id: str = "run-001",
    task_id: str = "T-001",
    url: str | None = None,
    title: str = "Test Source",
    publisher: str = "Test Pub",
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        run_id=run_id,
        research_task_id=task_id,
        perspective="Test",
        source=SourceResult(
            source_id="S-001",
            provider="fixture",
            title=title,
            url=url,
            source_type=SourceType.BLOG,
            publisher=publisher,
            retrieved_at=datetime.now(timezone.utc),
            snippet="Test snippet",
            provider_rank=1,
        ),
        authority_score=0.5,
        relevance_score=0.5,
        summary="Test summary",
        key_points=["Point 1"],
        supported_claims=["Claim 1"],
        limitations=[],
        status=EvidenceStatus.CANDIDATE,
    )


class TestLeadResearchAgent:

    def test_conduct_research_with_fixture_provider(self) -> None:
        provider = FixtureSourceProvider(case_id=FIXTURE_CASE)
        brief = ResearchBrief(
            run_id="run-001",
            objective="Compare multi-agent frameworks",
            scope_boundaries=["AI frameworks"],
            assumptions=[],
            open_clarifications=[],
            perspectives=["orchestration model"],
            success_criteria=["Coverage"],
            research_tasks=[
                ResearchTask(
                    research_task_id="T-001",
                    run_id="run-001",
                    perspective="orchestration model",
                    objective="Research orchestration",
                    query="How do frameworks handle orchestration?",
                    source_limit=1,
                ),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = LeadResearchAgent(max_concurrent=1)
            evidence = agent.conduct_research(
                brief=brief,
                provider=provider,
                run_id="run-001",
                run_dir=Path(tmpdir),
            )
            assert len(evidence) > 0
            for e in evidence:
                assert e.evidence_id.startswith("EV-run-001-")
                assert e.run_id == "run-001"
                assert e.status == EvidenceStatus.CANDIDATE

    def test_evidence_id_ordering_sequential(self) -> None:
        """Evidence IDs are assigned sequentially."""
        provider = FixtureSourceProvider(case_id=FIXTURE_CASE)
        brief = _make_brief(
            tasks=[
                ResearchTask(
                    research_task_id="T-A",
                    run_id="run-002",
                    perspective="orchestration model",
                    objective="First task",
                    query="How do frameworks handle orchestration?",
                ),
                ResearchTask(
                    research_task_id="T-B",
                    run_id="run-002",
                    perspective="production readiness",
                    objective="Second task",
                    query="What is the production readiness?",
                ),
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = LeadResearchAgent(max_concurrent=1)
            evidence = agent.conduct_research(
                brief=brief,
                provider=provider,
                run_id="run-002",
                run_dir=Path(tmpdir),
            )

            assert len(evidence) > 0
            ids = [e.evidence_id for e in evidence]
            # Verify IDs are sequential and follow expected format
            for i, id_str in enumerate(ids, start=1):
                assert id_str.startswith(f"EV-run-002-")
                parts = id_str.split("-")
                assert len(parts) >= 4
                # The sequence number part should be sequential
                assert int(parts[-1]) == i, f"Expected seq {i}, got {parts[-1]}"

    def test_dedup_two_tasks_same_url(self) -> None:
        """Two tasks returning evidence with same URL → only one stored."""
        evidence_a = _make_evidence(
            evidence_id="tmp-1",
            run_id="run-003",
            task_id="T-A",
            url="https://example.com/report",
            title="Same Report",
        )
        evidence_b = _make_evidence(
            evidence_id="tmp-2",
            run_id="run-003",
            task_id="T-B",
            url="https://example.com/report",
            title="Same Report",
        )
        k1 = dedupe_key(evidence_a)
        k2 = dedupe_key(evidence_b)
        assert k1 == k2, "Same URL should produce same dedupe key"

        seen_keys: set[tuple[str, str]] = set()
        accepted: list[Evidence] = []
        for candidate, seq in [(evidence_a, 1), (evidence_b, 2)]:
            key = dedupe_key(candidate)
            if key not in seen_keys:
                seen_keys.add(key)
                candidate = candidate.model_copy(
                    update={"evidence_id": f"EV-run-003-{seq:03d}"}
                )
                accepted.append(candidate)

        assert len(accepted) == 1
        assert accepted[0].evidence_id == "EV-run-003-001"

    def test_conduct_research_returns_evidence(self) -> None:
        """Simple task with matching perspective returns evidence."""
        provider = FixtureSourceProvider(case_id=FIXTURE_CASE)
        brief = _make_brief(
            tasks=[
                ResearchTask(
                    research_task_id="T-001",
                    run_id="run-004",
                    perspective="orchestration model",
                    objective="Task A",
                    query="How do frameworks handle orchestration?",
                ),
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = LeadResearchAgent(max_concurrent=1)
            evidence = agent.conduct_research(
                brief=brief,
                provider=provider,
                run_id="run-004",
                run_dir=Path(tmpdir),
            )
            assert len(evidence) > 0

    def test_empty_research_tasks_returns_empty(self) -> None:
        """If brief has clarifications but no tasks, returns empty."""
        provider = FixtureSourceProvider(case_id=FIXTURE_CASE)
        brief = ResearchBrief(
            run_id="run-005",
            objective="Test research",
            scope_boundaries=["test"],
            assumptions=[],
            open_clarifications=["Needs more info"],
            perspectives=[],
            success_criteria=[],
            research_tasks=[],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = LeadResearchAgent(max_concurrent=1)
            evidence = agent.conduct_research(
                brief=brief,
                provider=provider,
                run_id="run-005",
                run_dir=Path(tmpdir),
            )
            assert evidence == []

    def test_trace_events_recorded(self) -> None:
        """Trace contains RESEARCH_LEAD START/FINISH events."""
        provider = FixtureSourceProvider(case_id=FIXTURE_CASE)
        brief = _make_brief(
            tasks=[
                ResearchTask(
                    research_task_id="T-001",
                    run_id="run-006",
                    perspective="orchestration model",
                    objective="Task A",
                    query="How do frameworks handle orchestration?",
                    source_limit=1,
                ),
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            trace_path = Path(tmpdir) / "trace.jsonl"
            trace_writer = TraceWriter(trace_path)
            agent = LeadResearchAgent(max_concurrent=1)
            evidence = agent.conduct_research(
                brief=brief,
                provider=provider,
                run_id="run-006",
                run_dir=Path(tmpdir),
                trace_writer=trace_writer,
            )
            assert len(evidence) > 0

            events = trace_writer.read_all()
            lead_events = [
                e for e in events
                if e.agent_role in (AgentRole.RESEARCH_LEAD, AgentRole.RESEARCH_SUBAGENT)
            ]
            assert len(lead_events) > 0

            lead_starts = [
                e for e in lead_events
                if e.agent_role == AgentRole.RESEARCH_LEAD and e.event_type == EventType.START
            ]
            assert len(lead_starts) == 1

            lead_finishes = [
                e for e in lead_events
                if e.agent_role == AgentRole.RESEARCH_LEAD and e.event_type == EventType.FINISH
            ]
            assert len(lead_finishes) == 1

"""Tests for ResearchTaskAgent."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from traceresearch.agents.research_task_agent import ResearchTaskAgent
from traceresearch.agents.subagent_models import (
    CandidateEvidenceBatch,
    CompressedResearchContext,
    SubagentStatus,
)
from traceresearch.evidence.models import (
    Evidence,
    EvidenceStatus,
    ResearchTask,
)
from traceresearch.source_discovery.fixture_provider import FixtureSourceProvider


def _make_task(
    task_id: str = "T-run-001",
    run_id: str = "run-001",
    perspective: str = "Performance",
    query: str = "What is the latency?",
    source_limit: int = 2,
) -> ResearchTask:
    return ResearchTask(
        research_task_id=task_id,
        run_id=run_id,
        perspective=perspective,
        objective=f"Research {perspective}",
        query=query,
        source_limit=source_limit,
    )


def _make_context(
    run_id: str = "run-001",
    task: ResearchTask | None = None,
) -> CompressedResearchContext:
    return CompressedResearchContext(
        run_id=run_id,
        brief_summary="Test brief",
        task=task or _make_task(),
        provider_name="fixture",
        created_at=datetime.now(timezone.utc),
    )


class TestResearchTaskAgent:
    def test_compressed_context_does_not_leak_harness_references(self) -> None:
        """Verify CompressedResearchContext has no evidence_store or trace_writer."""
        ctx = _make_context()
        assert not hasattr(ctx, "evidence_store")
        assert not hasattr(ctx, "trace_writer")
        assert not hasattr(ctx, "writer")
        assert not hasattr(ctx, "verifier")
        assert not hasattr(ctx, "critic")
        assert not hasattr(ctx, "harness")

    def test_uses_fixture_provider_correctly(self) -> None:
        """Integration-style test: ResearchTaskAgent calls provider search + fetch."""
        provider = FixtureSourceProvider(case_id="001-framework-comparison")
        task = _make_task(
            perspective="orchestration model",
            query="How do LangGraph, AutoGen, and CrewAI handle agent orchestration?",
        )
        agent = ResearchTaskAgent()
        ctx = CompressedResearchContext(
            run_id="run-001",
            brief_summary="Compare multi-agent frameworks",
            task=task,
            provider_name="fixture",
        )

        batch = agent.execute(context=ctx, provider=provider)
        assert isinstance(batch, CandidateEvidenceBatch)
        assert batch.task_id == task.research_task_id
        assert batch.subagent_id is not None
        assert batch.status == SubagentStatus.SUCCESS
        assert len(batch.candidates) > 0
        for evidence in batch.candidates:
            assert isinstance(evidence, Evidence)
            assert evidence.run_id == "run-001"
            assert evidence.status == EvidenceStatus.CANDIDATE

    def test_empty_search_returns_partial_batch(self) -> None:
        """If provider.search returns no results, batch status is PARTIAL."""
        mock_provider = MagicMock()
        mock_provider.search.return_value = []
        task = _make_task()
        agent = ResearchTaskAgent()
        ctx = _make_context(task=task)

        batch = agent.execute(context=ctx, provider=mock_provider)
        assert batch.status == SubagentStatus.PARTIAL
        assert batch.candidates == []

    def test_provider_error_returns_failed_batch(self) -> None:
        """If provider.search raises, batch status is FAILED with error info."""
        mock_provider = MagicMock()
        mock_provider.search.side_effect = RuntimeError("Connection refused")
        task = _make_task()
        agent = ResearchTaskAgent()
        ctx = _make_context(task=task)

        batch = agent.execute(context=ctx, provider=mock_provider)
        assert batch.status == SubagentStatus.FAILED
        assert batch.error is not None
        assert "Connection refused" in str(batch.error.message)

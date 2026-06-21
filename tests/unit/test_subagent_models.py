"""Tests for subagent data models."""

from __future__ import annotations

from datetime import datetime, timezone

from traceresearch.agents.subagent_models import (
    CandidateEvidenceBatch,
    CompressedResearchContext,
    SubagentStatus,
)
from traceresearch.evidence.models import ResearchTask, ResearchTaskStatus
from traceresearch.trace.models import ErrorInfo


def test_subagent_status_enum_values() -> None:
    assert SubagentStatus.SUCCESS == "success"
    assert SubagentStatus.PARTIAL == "partial"
    assert SubagentStatus.FAILED == "failed"
    assert SubagentStatus.TIMED_OUT == "timed_out"


def test_compressed_research_context_fields() -> None:
    task = ResearchTask(
        research_task_id="T-run-001",
        run_id="run-001",
        perspective="Performance",
        objective="Measure latency",
        query="What is the latency?",
    )
    ctx = CompressedResearchContext(
        run_id="run-001",
        brief_summary="Test brief summary",
        task=task,
        provider_name="fixture",
    )
    assert ctx.run_id == "run-001"
    assert ctx.brief_summary == "Test brief summary"
    assert ctx.task.research_task_id == "T-run-001"
    assert ctx.provider_name == "fixture"
    assert isinstance(ctx.created_at, datetime)


def test_candidate_evidence_batch_defaults() -> None:
    batch = CandidateEvidenceBatch(
        task_id="T-run-001",
        subagent_id="SA-run-001-001",
    )
    assert batch.task_id == "T-run-001"
    assert batch.subagent_id == "SA-run-001-001"
    assert batch.status == SubagentStatus.SUCCESS
    assert batch.candidates == []
    assert batch.error is None


def test_candidate_evidence_batch_with_error() -> None:
    error = ErrorInfo(type="ProviderError", message="Connection timeout")
    batch = CandidateEvidenceBatch(
        task_id="T-run-002",
        subagent_id="SA-run-002-002",
        status=SubagentStatus.FAILED,
        error=error,
    )
    assert batch.status == SubagentStatus.FAILED
    assert batch.error is not None
    assert batch.error.type == "ProviderError"
    assert batch.error.message == "Connection timeout"


def test_candidate_evidence_batch_timed_out() -> None:
    batch = CandidateEvidenceBatch(
        task_id="T-run-003",
        subagent_id="SA-run-003-003",
        status=SubagentStatus.TIMED_OUT,
        error=ErrorInfo(type="TimeoutError", message="Task exceeded time limit"),
    )
    assert batch.status == SubagentStatus.TIMED_OUT
    assert batch.error is not None

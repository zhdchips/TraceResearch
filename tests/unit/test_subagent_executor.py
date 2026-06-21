"""Tests for SubagentExecutor bounded concurrency."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from traceresearch.agents.subagent_executor import SubagentExecutor
from traceresearch.agents.subagent_models import (
    CandidateEvidenceBatch,
    CompressedResearchContext,
    SubagentStatus,
)
from traceresearch.evidence.models import ResearchTask
from traceresearch.trace.models import ErrorInfo


def _make_task(task_id: str, query: str = "test query") -> ResearchTask:
    return ResearchTask(
        research_task_id=task_id,
        run_id="run-001",
        perspective="Test",
        objective="Test objective",
        query=query,
    )


def _make_agent_factory(delay: float = 0.0, fail: bool = False):
    """Return a factory that produces a simple ResearchTaskAgent callable."""

    def factory(context: CompressedResearchContext):
        if delay > 0:
            time.sleep(delay)
        if fail:
            return CandidateEvidenceBatch(
                task_id=context.task.research_task_id,
                subagent_id=f"SA-{context.run_id}-{context.task.research_task_id}",
                status=SubagentStatus.FAILED,
                error=ErrorInfo(type="TestError", message="Simulated failure"),
            )
        return CandidateEvidenceBatch(
            task_id=context.task.research_task_id,
            subagent_id=f"SA-{context.run_id}-{context.task.research_task_id}",
            status=SubagentStatus.SUCCESS,
        )

    return factory


class TestSubagentExecutor:
    def test_executes_all_tasks_with_concurrency_2(self) -> None:
        tasks = [_make_task("T-001"), _make_task("T-002"), _make_task("T-003")]
        executor = SubagentExecutor(max_workers=2)
        results = executor.execute(tasks, _make_agent_factory(delay=0.05))

        assert len(results) == 3
        task_ids = {r.task_id for r in results}
        assert task_ids == {"T-001", "T-002", "T-003"}
        assert all(r.status == SubagentStatus.SUCCESS for r in results)

    def test_failure_isolation_one_fails_two_succeed(self) -> None:
        tasks = [_make_task("T-001"), _make_task("T-002"), _make_task("T-003")]

        def mixed_factory(context: CompressedResearchContext):
            if context.task.research_task_id == "T-002":
                return CandidateEvidenceBatch(
                    task_id=context.task.research_task_id,
                    subagent_id=f"SA-{context.run_id}-002",
                    status=SubagentStatus.FAILED,
                    error=ErrorInfo(type="ProviderError", message="Simulated failure"),
                )
            return CandidateEvidenceBatch(
                task_id=context.task.research_task_id,
                subagent_id=f"SA-{context.run_id}-{context.task.research_task_id}",
                status=SubagentStatus.SUCCESS,
            )

        executor = SubagentExecutor(max_workers=2)
        results = executor.execute(tasks, mixed_factory)

        assert len(results) == 3
        successes = [r for r in results if r.status == SubagentStatus.SUCCESS]
        failures = [r for r in results if r.status == SubagentStatus.FAILED]
        assert len(successes) == 2
        assert len(failures) == 1
        assert failures[0].task_id == "T-002"
        assert failures[0].error is not None
        assert failures[0].error.type == "ProviderError"

    def test_concurrency_1_serial_order(self) -> None:
        tasks = [_make_task("T-001"), _make_task("T-002"), _make_task("T-003")]
        completion_order: list[str] = []

        def tracking_factory(context: CompressedResearchContext):
            completion_order.append(context.task.research_task_id)
            return CandidateEvidenceBatch(
                task_id=context.task.research_task_id,
                subagent_id=f"SA-{context.run_id}-{context.task.research_task_id}",
            )

        executor = SubagentExecutor(max_workers=1)
        results = executor.execute(tasks, tracking_factory)

        assert len(results) == 3
        # With max_workers=1, tasks should complete in submission order
        assert completion_order == ["T-001", "T-002", "T-003"]

    def test_timeout_marks_task_as_timed_out_and_does_not_block(self) -> None:
        tasks = [_make_task("T-001")]
        executor = SubagentExecutor(max_workers=1, task_timeout=0.1)

        def slow_factory(context: CompressedResearchContext):
            time.sleep(5.0)  # Far longer than timeout
            return CandidateEvidenceBatch(
                task_id=context.task.research_task_id,
                subagent_id="SA-001",
            )

        start = time.monotonic()
        results = executor.execute([tasks[0]], slow_factory)
        elapsed = time.monotonic() - start

        assert len(results) == 1
        assert results[0].status == SubagentStatus.TIMED_OUT
        # Executor must return quickly (within ~2x timeout + overhead)
        assert elapsed < 2.0, f"Executor blocked for {elapsed:.1f}s, expected <2s"

    def test_empty_task_list_returns_empty(self) -> None:
        executor = SubagentExecutor(max_workers=2)
        results = executor.execute([], _make_agent_factory())
        assert results == []

    def test_all_tasks_fail(self) -> None:
        tasks = [_make_task("T-001"), _make_task("T-002")]

        def failing_factory(context: CompressedResearchContext):
            return CandidateEvidenceBatch(
                task_id=context.task.research_task_id,
                subagent_id=f"SA-{context.run_id}-fail",
                status=SubagentStatus.FAILED,
                error=ErrorInfo(type="TestError", message="All fail"),
            )

        executor = SubagentExecutor(max_workers=2)
        results = executor.execute(tasks, failing_factory)

        assert len(results) == 2
        assert all(r.status == SubagentStatus.FAILED for r in results)

    def test_exception_in_factory_is_caught(self) -> None:
        tasks = [_make_task("T-001"), _make_task("T-002")]

        def exploding_factory(context: CompressedResearchContext):
            if context.task.research_task_id == "T-001":
                raise RuntimeError("Boom!")
            return CandidateEvidenceBatch(
                task_id=context.task.research_task_id,
                subagent_id="SA-002",
            )

        executor = SubagentExecutor(max_workers=2)
        results = executor.execute(tasks, exploding_factory)

        assert len(results) == 2
        failed = [r for r in results if r.status == SubagentStatus.FAILED]
        success = [r for r in results if r.status == SubagentStatus.SUCCESS]
        assert len(failed) == 1
        assert len(success) == 1
        assert failed[0].task_id == "T-001"
        assert failed[0].error is not None

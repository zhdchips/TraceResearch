"""Bounded-concurrency SubagentExecutor using ThreadPoolExecutor."""

from __future__ import annotations

import concurrent.futures
import os
from collections.abc import Callable
from datetime import datetime, timezone

from traceresearch.agents.subagent_models import (
    CandidateEvidenceBatch,
    CompressedResearchContext,
    SubagentStatus,
)
from traceresearch.evidence.models import ResearchTask
from traceresearch.trace.models import ErrorInfo

AgentFactory = Callable[[CompressedResearchContext], CandidateEvidenceBatch]


def _resolve_max_workers(default: int = 3) -> int:
    env_value = os.environ.get("TRACERESEARCH_MAX_CONCURRENT_RESEARCH_TASKS", "")
    if env_value:
        try:
            parsed = int(env_value)
            if parsed >= 1:
                return parsed
        except ValueError:
            pass
    return default


class SubagentExecutor:
    """Executes research tasks concurrently with bounded concurrency.

    Uses ThreadPoolExecutor for I/O-bound parallelism. Each task is dispatched
    to a separate thread. Failures are isolated — a single failed subagent
    does not affect other tasks.

    When task_timeout is set, slow tasks are marked TIMED_OUT and the executor
    returns without waiting for them (using pool.shutdown(wait=False)).
    """

    def __init__(
        self,
        *,
        max_workers: int | None = None,
        task_timeout: float | None = None,
    ) -> None:
        self.max_workers = max_workers if max_workers is not None else _resolve_max_workers()
        self.task_timeout = task_timeout

    def execute(
        self,
        tasks: list[ResearchTask],
        agent_factory: AgentFactory,
    ) -> list[CandidateEvidenceBatch]:
        if not tasks:
            return []

        results: list[CandidateEvidenceBatch] = []
        futures_to_tasks: dict[concurrent.futures.Future[CandidateEvidenceBatch], ResearchTask] = {}
        completed: set[concurrent.futures.Future[CandidateEvidenceBatch]] = set()

        pool = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
        try:
            for task in tasks:
                future = pool.submit(
                    _run_agent,
                    agent_factory=agent_factory,
                    task=task,
                )
                futures_to_tasks[future] = task

            # Wait for results with optional timeout.
            try:
                for future in concurrent.futures.as_completed(
                    futures_to_tasks,
                    timeout=self.task_timeout,
                ):
                    completed.add(future)
                    task = futures_to_tasks[future]
                    try:
                        result = future.result(timeout=0)
                        results.append(result)
                    except Exception as exc:
                        results.append(
                            CandidateEvidenceBatch(
                                task_id=task.research_task_id,
                                subagent_id=f"SA-{task.run_id}-error",
                                status=SubagentStatus.FAILED,
                                error=ErrorInfo(
                                    type=type(exc).__name__,
                                    message=str(exc),
                                ),
                            )
                        )
            except concurrent.futures.TimeoutError:
                pass  # as_completed timeout — remaining futures didn't finish in time
        finally:
            # Shutdown without waiting: slow threads will finish on their own.
            # This prevents the caller from being blocked by hung tasks.
            pool.shutdown(wait=False)

        # Mark any futures that didn't complete as timed out.
        for future, task in futures_to_tasks.items():
            if future not in completed:
                results.append(
                    CandidateEvidenceBatch(
                        task_id=task.research_task_id,
                        subagent_id=f"SA-{task.run_id}-timeout",
                        status=SubagentStatus.TIMED_OUT,
                        error=ErrorInfo(
                            type="TimeoutError",
                            message=(
                                f"Task {task.research_task_id} exceeded "
                                f"timeout of {self.task_timeout}s"
                            ),
                        ),
                    )
                )

        return results


def _run_agent(
    *,
    agent_factory: AgentFactory,
    task: ResearchTask,
) -> CandidateEvidenceBatch:
    """Run a single agent in a thread. Creates a CompressedResearchContext from the task."""
    context = CompressedResearchContext(
        run_id=task.run_id,
        brief_summary=f"Research task: {task.objective}",
        task=task,
        provider_name="",  # Will be enriched by the caller's factory
    )
    return agent_factory(context)

"""LeadResearchAgent — orchestrates research tasks via subagent execution."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from traceresearch.agents.research_task_agent import ResearchTaskAgent
from traceresearch.agents.subagent_executor import SubagentExecutor, _resolve_max_workers
from traceresearch.agents.subagent_models import (
    CandidateEvidenceBatch,
    CompressedResearchContext,
    SubagentStatus,
)
from traceresearch.evidence.models import Evidence, ResearchBrief
from traceresearch.evidence.store import EvidenceStore, dedupe_key
from traceresearch.source_discovery.base import SourceDiscoveryProvider
from traceresearch.trace.models import (
    AgentRole,
    ErrorInfo,
    EventType,
    TraceEvent,
    TraceStatus,
)
from traceresearch.trace.writer import TraceWriter


def _resolve_task_timeout(default: float | None = None) -> float | None:
    env_value = os.environ.get("TRACERESEARCH_RESEARCH_TASK_TIMEOUT_SECONDS", "")
    if env_value:
        try:
            parsed = float(env_value)
            if parsed > 0:
                return parsed
        except ValueError:
            pass
    return default


@dataclass
class LeadResearchResult:
    """Result from conduct_research() — evidence + failure metadata."""

    evidence: list[Evidence] = field(default_factory=list)
    failed_task_ids: list[str] = field(default_factory=list)


class LeadResearchAgent:
    """Lead agent that dispatches research tasks to subagents and collects results.

    Responsibilities:
    - Dispatch research_tasks via SubagentExecutor
    - Deduplicate evidence across subagent results
    - Assign stable evidence IDs in task definition order
    - Write evidence to EvidenceStore
    - Record lifecycle trace events (thread-safe via TraceWriter)
    """

    def __init__(
        self,
        *,
        max_concurrent: int | None = None,
        task_timeout: float | None = None,
    ) -> None:
        self.max_concurrent = (
            max_concurrent if max_concurrent is not None else _resolve_max_workers()
        )
        self.task_timeout = (
            task_timeout if task_timeout is not None else _resolve_task_timeout()
        )
        self._task_agent = ResearchTaskAgent()

    def conduct_research(
        self,
        *,
        brief: ResearchBrief,
        provider: SourceDiscoveryProvider,
        run_id: str,
        run_dir: str | Path,
        trace_writer: TraceWriter | None = None,
        provider_tool_name: str | None = None,
    ) -> LeadResearchResult:
        run_dir = Path(run_dir)
        tasks = brief.research_tasks

        if not tasks:
            return LeadResearchResult()

        # Initialize evidence store
        evidence_path = run_dir / "evidence.jsonl"
        evidence_store = EvidenceStore(evidence_path)
        provider_name = provider.provider_name

        # Trace: lead start
        self._trace(
            trace_writer,
            run_id,
            AgentRole.RESEARCH_LEAD,
            EventType.START,
            f"dispatching {len(tasks)} research tasks",
            f"max_concurrent={self.max_concurrent} task_timeout={self.task_timeout}",
            status=TraceStatus.SUCCESS,
        )

        # Build agent factory — runs in worker thread
        def agent_factory(ctx: CompressedResearchContext) -> CandidateEvidenceBatch:
            enriched_ctx = CompressedResearchContext(
                run_id=ctx.run_id,
                brief_summary=ctx.brief_summary,
                task=ctx.task,
                provider_name=provider_name,
            )
            subagent_id = f"SA-{run_id}-{ctx.task.research_task_id}"
            # Trace: subagent start (thread-safe via TraceWriter)
            self._trace(
                trace_writer,
                run_id,
                AgentRole.RESEARCH_SUBAGENT,
                EventType.START,
                f"task={ctx.task.research_task_id} perspective={ctx.task.perspective}",
                f"subagent_id={subagent_id}",
                task_id=ctx.task.research_task_id,
                subagent_id=subagent_id,
                tool_name=provider_tool_name,
                status=TraceStatus.SUCCESS,
            )

            try:
                batch = self._task_agent.execute(context=enriched_ctx, provider=provider)

                finish_status = TraceStatus.SUCCESS
                if batch.status == SubagentStatus.FAILED:
                    finish_status = TraceStatus.FAILED
                elif batch.status == SubagentStatus.TIMED_OUT:
                    finish_status = TraceStatus.FAILED

                self._trace(
                    trace_writer,
                    run_id,
                    AgentRole.RESEARCH_SUBAGENT,
                    EventType.FINISH,
                    f"task={ctx.task.research_task_id}",
                    f"status={batch.status.value} candidates={len(batch.candidates)}",
                    task_id=ctx.task.research_task_id,
                    subagent_id=subagent_id,
                    tool_name=provider_tool_name,
                    status=finish_status,
                    error=batch.error if batch.error else None,
                )
                return batch
            except Exception as exc:
                self._trace(
                    trace_writer,
                    run_id,
                    AgentRole.RESEARCH_SUBAGENT,
                    EventType.ERROR,
                    f"task={ctx.task.research_task_id}",
                    str(exc),
                    task_id=ctx.task.research_task_id,
                    subagent_id=subagent_id,
                    tool_name=provider_tool_name,
                    status=TraceStatus.FAILED,
                    error=ErrorInfo(type=type(exc).__name__, message=str(exc)),
                )
                raise

        executor = SubagentExecutor(
            max_workers=self.max_concurrent,
            task_timeout=self.task_timeout,
        )

        start_time = datetime.now(timezone.utc)
        batches = executor.execute(tasks, agent_factory)
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

        # --- Write tool events single-threaded (after all subagents complete) ---
        for batch in batches:
            for te in batch.tool_events:
                ev_status = TraceStatus.SUCCESS if te.status == "success" else TraceStatus.FAILED
                ev_type = EventType.TOOL_CALL if te.event_type == "tool_call" else EventType.TOOL_RESULT
                self._trace(
                    trace_writer,
                    run_id,
                    AgentRole.RESEARCH_SUBAGENT,
                    ev_type,
                    te.input_summary,
                    te.output_summary,
                    task_id=batch.task_id,
                    subagent_id=batch.subagent_id,
                    tool_name=te.tool_name,
                    status=ev_status,
                    error=te.error,
                )

        # Trace: lead tool result
        total_candidates = sum(len(b.candidates) for b in batches)
        failed_task_ids = [
            b.task_id for b in batches
            if b.status in (SubagentStatus.FAILED, SubagentStatus.TIMED_OUT)
        ]
        self._trace(
            trace_writer,
            run_id,
            AgentRole.RESEARCH_LEAD,
            EventType.TOOL_RESULT,
            f"executor returned {len(batches)} batches in {elapsed:.1f}s",
            f"total_candidates={total_candidates} failed_tasks={len(failed_task_ids)}",
            status=TraceStatus.SUCCESS,
        )

        # If all failed, return empty with failed_task_ids
        if all(b.status in (SubagentStatus.FAILED, SubagentStatus.TIMED_OUT) for b in batches):
            first_error = next(
                (b.error for b in batches if b.error is not None), None
            )
            self._trace(
                trace_writer,
                run_id,
                AgentRole.RESEARCH_LEAD,
                EventType.FINISH,
                "all tasks failed",
                f"failed_task_ids={failed_task_ids}",
                status=TraceStatus.FAILED,
                error=first_error or ErrorInfo(
                    type="AllTasksFailed",
                    message="All research tasks failed or timed out",
                ),
            )
            return LeadResearchResult(failed_task_ids=failed_task_ids)

        # Dedup and assign evidence IDs in task definition order
        stored_evidence: list[Evidence] = []
        seen_keys: set[tuple[str, str]] = set()
        sequence = 1

        # Process batches in task definition order
        task_order = {task.research_task_id: i for i, task in enumerate(tasks)}
        sorted_batches = sorted(
            batches,
            key=lambda b: task_order.get(b.task_id, len(tasks)),
        )

        for batch in sorted_batches:
            if batch.status in (SubagentStatus.FAILED, SubagentStatus.TIMED_OUT):
                continue
            for candidate in batch.candidates:
                key = dedupe_key(candidate)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                evidence = candidate.model_copy(
                    update={
                        "evidence_id": f"EV-{run_id}-{sequence:03d}",
                        "run_id": run_id,
                    }
                )
                stored = evidence_store.add(evidence)
                if stored.evidence_id not in {
                    existing.evidence_id for existing in stored_evidence
                }:
                    stored_evidence.append(stored)
                sequence += 1

        # Trace: lead finish
        self._trace(
            trace_writer,
            run_id,
            AgentRole.RESEARCH_LEAD,
            EventType.FINISH,
            "research phase complete",
            f"stored={len(stored_evidence)} evidence "
            f"dedup_skipped={total_candidates - len(stored_evidence)} "
            f"failed_tasks={failed_task_ids} "
            f"elapsed={elapsed:.1f}s",
            status=TraceStatus.SUCCESS,
        )

        return LeadResearchResult(
            evidence=stored_evidence,
            failed_task_ids=failed_task_ids,
        )

    @staticmethod
    def _trace(
        writer: TraceWriter | None,
        run_id: str,
        agent_role: AgentRole,
        event_type: EventType,
        input_summary: str,
        output_summary: str,
        *,
        task_id: str | None = None,
        subagent_id: str | None = None,
        tool_name: str | None = None,
        status: TraceStatus = TraceStatus.SUCCESS,
        error: ErrorInfo | None = None,
    ) -> None:
        if writer is None:
            return
        # Thread-safe via TraceWriter's internal lock and sequence
        trace_id = writer.next_trace_id(run_id)
        event = TraceEvent(
            trace_id=trace_id,
            run_id=run_id,
            task_id=task_id,
            subagent_id=subagent_id,
            agent_role=agent_role,
            event_type=event_type,
            tool_name=tool_name,
            input_summary=input_summary,
            output_summary=output_summary,
            status=status,
            latency_ms=0,
            error=error,
            created_at=datetime.now(timezone.utc),
        )
        writer.append(event)

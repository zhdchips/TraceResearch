"""ResearchTaskAgent — single-task subagent that returns candidate evidence."""

from __future__ import annotations

from traceresearch.agents.researcher import Researcher
from traceresearch.agents.subagent_models import (
    CandidateEvidenceBatch,
    CompressedResearchContext,
    SubagentStatus,
)
from traceresearch.source_discovery.base import (
    SourceDiscoveryError,
    SourceDiscoveryProvider,
    SourceRef,
)
from traceresearch.trace.models import ErrorInfo


class ResearchTaskAgent:
    """Executes a single ResearchTask against a SourceDiscoveryProvider.

    A callable subagent that receives only compressed context (no full harness).
    Returns a CandidateEvidenceBatch — LeadResearchAgent handles dedup and
    Evidence Store writing.
    """

    def __init__(self) -> None:
        self._researcher = Researcher()

    def execute(
        self,
        *,
        context: CompressedResearchContext,
        provider: SourceDiscoveryProvider,
    ) -> CandidateEvidenceBatch:
        subagent_id = f"SA-{context.run_id}-{context.task.research_task_id}"
        try:
            evidence_items: list = self._researcher.research(
                run_id=context.run_id,
                task=context.task,
                provider=provider,
                start_index=1,
            )
            if not evidence_items:
                return CandidateEvidenceBatch(
                    task_id=context.task.research_task_id,
                    subagent_id=subagent_id,
                    status=SubagentStatus.PARTIAL,
                )
            return CandidateEvidenceBatch(
                task_id=context.task.research_task_id,
                subagent_id=subagent_id,
                status=SubagentStatus.SUCCESS,
                candidates=evidence_items,
            )
        except SourceDiscoveryError as exc:
            # Use the provider's trace_error method for proper error codes
            to_trace_error = getattr(exc, "to_trace_error", None)
            if callable(to_trace_error):
                trace_error = to_trace_error()
            else:
                trace_error = ErrorInfo(type=exc.code, message=str(exc))
            return CandidateEvidenceBatch(
                task_id=context.task.research_task_id,
                subagent_id=subagent_id,
                status=SubagentStatus.FAILED,
                error=trace_error,
            )
        except Exception as exc:
            return CandidateEvidenceBatch(
                task_id=context.task.research_task_id,
                subagent_id=subagent_id,
                status=SubagentStatus.FAILED,
                error=ErrorInfo(
                    type=type(exc).__name__,
                    message=str(exc),
                ),
            )

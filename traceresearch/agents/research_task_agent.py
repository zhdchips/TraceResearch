"""ResearchTaskAgent — single-task subagent that returns candidate evidence."""

from __future__ import annotations

from traceresearch.agents.researcher import Researcher
from traceresearch.agents.subagent_models import (
    CandidateEvidenceBatch,
    CompressedResearchContext,
    SubagentStatus,
    ToolEvent,
)
from traceresearch.source_discovery.base import (
    SourceDiscoveryError,
    SourceDiscoveryProvider,
    SourceRef,
)
from traceresearch.trace.models import ErrorInfo


def _provider_tool_name(provider: SourceDiscoveryProvider) -> str:
    """Resolve the tool name for a source provider (same logic as orchestrator)."""
    explicit_tool_name = getattr(provider, "tool_name", None)
    if explicit_tool_name:
        return str(explicit_tool_name)
    if provider.provider_name == "fixture":
        return "fixture.search"
    provider_display_name = getattr(provider, "provider_display_name", None)
    if provider_display_name == "exa":
        return "exa.search"
    if provider.provider_name == "web":
        return "web_search"
    return f"{provider.provider_name}.search"


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
        tool_name = _provider_tool_name(provider)
        tool_events: list[ToolEvent] = []

        try:
            # --- TOOL_CALL: search ---
            tool_events.append(
                ToolEvent(
                    event_type="tool_call",
                    tool_name=tool_name,
                    input_summary=f"search: {context.task.query[:120]}",
                    output_summary="",
                    status="success",
                )
            )

            evidence_items: list = self._researcher.research(
                run_id=context.run_id,
                task=context.task,
                provider=provider,
                start_index=1,
            )

            # --- TOOL_RESULT: search ---
            source_ids = [e.source.source_id for e in evidence_items]
            tool_events.append(
                ToolEvent(
                    event_type="tool_result",
                    tool_name=tool_name,
                    input_summary=f"search: {context.task.query[:120]}",
                    output_summary=f"result_count={len(evidence_items)} source_ids={','.join(source_ids[:10])}",
                    status="success",
                )
            )

            if not evidence_items:
                return CandidateEvidenceBatch(
                    task_id=context.task.research_task_id,
                    subagent_id=subagent_id,
                    status=SubagentStatus.PARTIAL,
                    tool_events=tool_events,
                )
            return CandidateEvidenceBatch(
                task_id=context.task.research_task_id,
                subagent_id=subagent_id,
                status=SubagentStatus.SUCCESS,
                candidates=evidence_items,
                tool_events=tool_events,
            )
        except SourceDiscoveryError as exc:
            # --- TOOL_RESULT: error ---
            to_trace_error = getattr(exc, "to_trace_error", None)
            if callable(to_trace_error):
                trace_error = to_trace_error()
            else:
                trace_error = ErrorInfo(type=exc.code, message=str(exc))
            tool_events.append(
                ToolEvent(
                    event_type="tool_result",
                    tool_name=tool_name,
                    input_summary=f"search: {context.task.query[:120]}",
                    output_summary=f"error: {trace_error.type}",
                    status="failed",
                    error=trace_error,
                )
            )
            return CandidateEvidenceBatch(
                task_id=context.task.research_task_id,
                subagent_id=subagent_id,
                status=SubagentStatus.FAILED,
                error=trace_error,
                tool_events=tool_events,
            )
        except Exception as exc:
            tool_events.append(
                ToolEvent(
                    event_type="tool_result",
                    tool_name=tool_name,
                    input_summary=f"search: {context.task.query[:120]}",
                    output_summary=f"error: {type(exc).__name__}",
                    status="failed",
                    error=ErrorInfo(type=type(exc).__name__, message=str(exc)),
                )
            )
            return CandidateEvidenceBatch(
                task_id=context.task.research_task_id,
                subagent_id=subagent_id,
                status=SubagentStatus.FAILED,
                error=ErrorInfo(
                    type=type(exc).__name__,
                    message=str(exc),
                ),
                tool_events=tool_events,
            )

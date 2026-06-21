"""Data models for Research Subagent architecture."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from traceresearch.evidence.models import Evidence, ResearchTask
from traceresearch.trace.models import ErrorInfo


class SubagentStatus(StrEnum):
    """Execution status of a single ResearchTaskAgent."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass
class CompressedResearchContext:
    """Lightweight context passed to each ResearchTaskAgent.

    Contains only the information needed to execute a single research task.
    Excludes EvidenceStore, TraceWriter, Writer, Verifier, and other harness components.
    """

    run_id: str
    brief_summary: str
    task: ResearchTask
    provider_name: str
    created_at: datetime = field(default_factory=lambda: datetime.now())


@dataclass
class ToolEvent:
    """Lightweight record of a provider tool call within a subagent.

    Collected by ResearchTaskAgent and written to trace by LeadResearchAgent
    (single-threaded, after all subagents complete).
    """

    event_type: str  # "tool_call" or "tool_result"
    tool_name: str
    input_summary: str
    output_summary: str
    status: str  # "success" or "failed"
    error: ErrorInfo | None = None


@dataclass
class CandidateEvidenceBatch:
    """Result from a single ResearchTaskAgent execution.

    Contains un-deduplicated evidence candidates with temporary IDs.
    The LeadResearchAgent is responsible for dedup and final ID assignment.
    """

    task_id: str
    subagent_id: str
    status: SubagentStatus = SubagentStatus.SUCCESS
    candidates: list[Evidence] = field(default_factory=list)
    error: ErrorInfo | None = None
    tool_events: list[ToolEvent] = field(default_factory=list)


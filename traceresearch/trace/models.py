"""Trace event models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TraceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentRole(StrEnum):
    PLANNER = "Planner"
    RESEARCHER = "Researcher"
    VERIFIER = "Verifier"
    CRITIC = "Critic"
    WRITER = "Writer"
    EVAL_RUNNER = "EvalRunner"
    HARNESS = "Harness"


class EventType(StrEnum):
    START = "start"
    FINISH = "finish"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    WARNING = "warning"
    ERROR = "error"


class TraceStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    NEEDS_CLARIFICATION = "needs_clarification"


class TokenUsage(TraceModel):
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class ErrorInfo(TraceModel):
    type: str | None = None
    message: str | None = None


class TraceEvent(TraceModel):
    trace_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    task_id: str | None = None
    agent_role: AgentRole
    event_type: EventType
    tool_name: str | None = None
    input_summary: str
    output_summary: str
    status: TraceStatus
    latency_ms: int = Field(ge=0)
    token_usage: TokenUsage | None = None
    error: ErrorInfo | None = None
    created_at: datetime

    @model_validator(mode="after")
    def failed_events_have_error_message(self) -> "TraceEvent":
        if self.status == TraceStatus.FAILED:
            if self.error is None or not self.error.message:
                raise ValueError("failed TraceEvent requires error.message")
        return self

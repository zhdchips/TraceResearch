"""Tests for LLM-specific TraceEvent fields — backward compatible."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from traceresearch.trace.models import (
    AgentRole,
    ErrorInfo,
    EventType,
    TokenUsage,
    TraceEvent,
    TraceStatus,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _minimal_event(**overrides) -> TraceEvent:
    kwargs = {
        "trace_id": "TR-test-001",
        "run_id": "test-run",
        "agent_role": AgentRole.WRITER,
        "event_type": EventType.START,
        "input_summary": "input",
        "output_summary": "output",
        "status": TraceStatus.SUCCESS,
        "latency_ms": 100,
        "created_at": datetime.now(timezone.utc),
        **overrides,
    }
    return TraceEvent(**kwargs)


# ---------------------------------------------------------------------------
# New field presence
# ---------------------------------------------------------------------------


class TestLLMFieldsPresence:
    def test_llm_mode_field_defaults_to_none(self):
        event = _minimal_event()
        assert event.llm_mode is None

    def test_llm_model_field_defaults_to_none(self):
        event = _minimal_event()
        assert event.llm_model is None

    def test_llm_token_usage_field_defaults_to_none(self):
        event = _minimal_event()
        assert event.llm_token_usage is None

    def test_failover_reason_field_defaults_to_none(self):
        event = _minimal_event()
        assert event.failover_reason is None

    def test_llm_mode_can_be_set_to_llm(self):
        event = _minimal_event(llm_mode="llm")
        assert event.llm_mode == "llm"

    def test_llm_mode_can_be_set_to_deterministic(self):
        event = _minimal_event(llm_mode="deterministic")
        assert event.llm_mode == "deterministic"

    def test_llm_model_stores_model_id(self):
        event = _minimal_event(llm_model="deepseek-chat")
        assert event.llm_model == "deepseek-chat"

    def test_llm_token_usage_stores_usage(self):
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        event = _minimal_event(llm_token_usage=usage)
        assert event.llm_token_usage.prompt_tokens == 100
        assert event.llm_token_usage.completion_tokens == 50
        assert event.llm_token_usage.total_tokens == 150

    def test_failover_reason_stores_reason(self):
        event = _minimal_event(failover_reason="timeout")
        assert event.failover_reason == "timeout"


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


class TestLLMFieldsBackwardCompatible:
    def test_old_json_without_new_fields_parses(self):
        """JSONL record without llm_* fields MUST deserialize successfully."""
        old_json = json.dumps(
            {
                "trace_id": "TR-old-001",
                "run_id": "old-run",
                "agent_role": "Writer",
                "event_type": "finish",
                "input_summary": "in",
                "output_summary": "out",
                "status": "success",
                "latency_ms": 50,
                "created_at": "2026-06-01T00:00:00Z",
            }
        )
        event = TraceEvent.model_validate_json(old_json)
        assert event.trace_id == "TR-old-001"
        assert event.llm_mode is None
        assert event.llm_model is None
        assert event.llm_token_usage is None
        assert event.failover_reason is None

    def test_roundtrip_preserves_llm_fields(self):
        event = _minimal_event(
            llm_mode="llm",
            llm_model="deepseek-chat",
            llm_token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            failover_reason=None,
        )
        dumped = event.model_dump_json()
        reloaded = TraceEvent.model_validate_json(dumped)
        assert reloaded.llm_mode == "llm"
        assert reloaded.llm_model == "deepseek-chat"
        assert reloaded.llm_token_usage is not None
        assert reloaded.llm_token_usage.total_tokens == 15
        assert reloaded.failover_reason is None

    def test_deterministic_event_has_no_llm_fields(self):
        """Default deterministic path MUST NOT have misleading LLM fields."""
        event = _minimal_event()  # no LLM fields set
        assert event.llm_mode is None
        assert event.llm_model is None
        assert event.llm_token_usage is None
        assert event.failover_reason is None
        # Serialization should exclude None values or keep them None
        dumped = event.model_dump(mode="json")
        assert dumped.get("llm_mode") is None
        assert dumped.get("failover_reason") is None

    def test_full_failover_event(self):
        """A failover event records all relevant info."""
        event = _minimal_event(
            agent_role=AgentRole.WRITER,
            event_type=EventType.ERROR,
            status=TraceStatus.FAILED,
            llm_mode="llm",
            llm_model="deepseek-chat",
            failover_reason="timeout",
            output_summary="LLM call failed: timeout after 60s",
            error=ErrorInfo(type="timeout", message="timed out"),
        )
        assert event.llm_mode == "llm"
        assert event.failover_reason == "timeout"
        assert event.error is not None
        assert event.error.type == "timeout"

    def test_partial_llm_fields_roundtrip(self):
        """Some LLM fields set, some None — roundtrips correctly."""
        event = _minimal_event(
            llm_mode="llm",
            llm_model="deepseek-chat",
        )
        dumped = event.model_dump_json()
        reloaded = TraceEvent.model_validate_json(dumped)
        assert reloaded.llm_mode == "llm"
        assert reloaded.llm_model == "deepseek-chat"
        assert reloaded.llm_token_usage is None
        assert reloaded.failover_reason is None

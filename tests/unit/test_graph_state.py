"""Unit tests for GraphState (009) — creation, sync, serialization."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from traceresearch.agents.graph_state import (
    GraphState,
    create_initial_graph_state,
    sync_from_runtime_state,
)
from traceresearch.agents.lead_runtime import LeadAgentRuntime, RuntimeState
from traceresearch.evidence.models import (
    CritiqueDecision,
    CritiqueResult,
    NextPhase,
)
from traceresearch.trace.writer import TraceWriter


class TestCreateInitialGraphState:
    def test_creates_with_required_fields(self, tmp_path):
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()

        state = RuntimeState(run_id="gst-001", run_dir=str(run_dir))
        runtime = LeadAgentRuntime(state=state)

        gs = create_initial_graph_state(
            run_id="gst-001",
            run_dir=str(run_dir),
            runtime_state=state,
            runtime=runtime,
            max_iterations=3,
        )

        assert gs["run_id"] == "gst-001"
        assert gs["run_dir"] == str(run_dir)
        assert gs["status"] == "initialized"
        assert gs["current_step"] == ""
        assert gs["next_phase"] == ""
        assert gs["iteration_index"] == 0
        assert gs["max_iterations"] == 3
        assert gs["critique_decision"] == ""
        assert gs["revision_reason"] == ""
        assert gs["error_message"] == ""
        assert gs["artifact_paths"] == {}

    def test_internal_refs_preserved(self, tmp_path):
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()

        state = RuntimeState(run_id="gst-002", run_dir=str(run_dir))
        runtime = LeadAgentRuntime(state=state)

        gs = create_initial_graph_state(
            run_id="gst-002",
            run_dir=str(run_dir),
            runtime_state=state,
            runtime=runtime,
        )

        assert gs["_runtime_state"] is state
        assert gs["_runtime"] is runtime


class TestSyncFromRuntimeState:
    def test_syncs_status(self, tmp_path):
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()

        state = RuntimeState(run_id="gst-003", run_dir=str(run_dir))
        runtime = LeadAgentRuntime(state=state)

        gs = create_initial_graph_state(
            run_id="gst-003",
            run_dir=str(run_dir),
            runtime_state=state,
            runtime=runtime,
        )

        state.status = "researched"
        state.iteration_index = 2
        state.next_phase = "write"

        gs = sync_from_runtime_state(gs)
        assert gs["status"] == "researched"
        assert gs["iteration_index"] == 2
        assert gs["next_phase"] == "write"

    def test_syncs_critique(self, tmp_path):
        run_dir = tmp_path / "test-run"
        run_dir.mkdir()

        state = RuntimeState(run_id="gst-004", run_dir=str(run_dir))
        runtime = LeadAgentRuntime(state=state)

        gs = create_initial_graph_state(
            run_id="gst-004",
            run_dir=str(run_dir),
            runtime_state=state,
            runtime=runtime,
        )

        state.critique_result = CritiqueResult(
            run_id="gst-004",
            missing_perspectives=["P2", "P3"],
            weak_sources=[],
            duplicate_sections=[],
            unsupported_claims=[],
            limitations_to_add=[],
            decision=CritiqueDecision.REVISE,
            next_phase=NextPhase.RESEARCH,
            failed_task_ids=[],
        )

        gs = sync_from_runtime_state(gs)
        assert gs["critique_decision"] == "revise"

    def test_sync_no_runtime_state(self):
        gs = GraphState(
            run_id="x",
            run_dir="/tmp/x",
            status="initialized",
            current_step="",
            next_phase="",
            iteration_index=0,
            max_iterations=1,
            critique_decision="",
            revision_reason="",
            error_message="",
            artifact_paths={},
        )
        # Should not raise
        result = sync_from_runtime_state(gs)
        assert result is gs

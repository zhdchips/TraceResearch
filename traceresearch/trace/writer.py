"""JSONL Trace writer — thread-safe append with monotonic sequence."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from traceresearch.trace.models import AgentRole
from traceresearch.trace.models import TraceEvent


REQUIRED_COMPLETED_RUN_ROLES = {
    AgentRole.PLANNER,
    AgentRole.RESEARCHER,
    AgentRole.VERIFIER,
    AgentRole.CRITIC,
    AgentRole.WRITER,
    AgentRole.HARNESS,
}


class TraceWriter:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._seq = 0

    def append(self, event: TraceEvent) -> None:
        """Thread-safe append — lock protects both sequence and file write."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = event.model_dump(mode="json")
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._lock:
            with self.path.open("a", encoding="utf-8") as file:
                file.write(line)

    def next_trace_id(self, run_id: str, prefix: str = "lead") -> str:
        """Return a monotonic unique trace_id. Thread-safe."""
        with self._lock:
            self._seq += 1
            return f"TR-{run_id}-{prefix}-{self._seq:03d}"

    def snapshot_sequence(self) -> int:
        """Return current sequence value (for testing). Thread-safe."""
        with self._lock:
            return self._seq

    def read_all(self) -> list[TraceEvent]:
        if not self.path.exists():
            return []
        events: list[TraceEvent] = []
        with self.path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                events.append(TraceEvent.model_validate_json(line))
        return events

    def validate_completed_run_coverage(
        self,
        required_roles: set[AgentRole] | None = None,
    ) -> None:
        required = required_roles or REQUIRED_COMPLETED_RUN_ROLES
        present = {event.agent_role for event in self.read_all()}
        missing = sorted(role.value for role in required - present)
        if missing:
            raise ValueError(f"completed run Trace is missing roles: {', '.join(missing)}")

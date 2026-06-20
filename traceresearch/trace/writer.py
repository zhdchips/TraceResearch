"""JSONL Trace writer."""

from __future__ import annotations

import json
from pathlib import Path

from traceresearch.trace.models import TraceEvent


class TraceWriter:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, event: TraceEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = event.model_dump(mode="json")
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
            file.write("\n")

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

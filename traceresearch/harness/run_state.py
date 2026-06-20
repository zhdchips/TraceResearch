"""Helpers for inspecting run artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from traceresearch.evidence.models import Evidence, ResearchRunStatus
from traceresearch.trace.models import TraceStatus
from traceresearch.trace.writer import TraceWriter


@dataclass(frozen=True)
class ReportPaths:
    final_report: Path
    report_json: Path


class RunState:
    def __init__(self, run_dir: str | Path) -> None:
        self.run_dir = Path(run_dir)

    def status(self) -> ResearchRunStatus:
        events = self.trace_events()
        if any(event.status == TraceStatus.FAILED for event in events):
            return ResearchRunStatus.FAILED
        if any(event.status == TraceStatus.NEEDS_CLARIFICATION for event in events):
            return ResearchRunStatus.NEEDS_CLARIFICATION
        if self._has_completed_artifacts():
            return ResearchRunStatus.COMPLETED
        return ResearchRunStatus.CREATED

    def evidence_by_id(self, evidence_id: str) -> Evidence | None:
        for evidence in self.evidence():
            if evidence.evidence_id == evidence_id:
                return evidence
        return None

    def evidence(self) -> list[Evidence]:
        path = self.run_dir / "evidence.jsonl"
        if not path.exists():
            return []
        return [
            Evidence.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def trace_events(self):
        return TraceWriter(self.run_dir / "trace.jsonl").read_all()

    def report_paths(self) -> ReportPaths:
        return ReportPaths(
            final_report=self.run_dir / "final_report.md",
            report_json=self.run_dir / "report.json",
        )

    def _has_completed_artifacts(self) -> bool:
        required = [
            "research_brief.json",
            "research_tasks.json",
            "evidence.jsonl",
            "verification.json",
            "critique.json",
            "outline.md",
            "draft_report.md",
            "final_report.md",
            "report.json",
            "trace.jsonl",
        ]
        return all((self.run_dir / name).exists() for name in required)

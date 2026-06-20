"""Run artifact path management."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REQUIRED_ARTIFACT_FILES = {
    "research_brief": "research_brief.json",
    "research_tasks": "research_tasks.json",
    "evidence": "evidence.jsonl",
    "verification": "verification.json",
    "critique": "critique.json",
    "outline": "outline.md",
    "draft_report": "draft_report.md",
    "final_report": "final_report.md",
    "report_json": "report.json",
    "trace": "trace.jsonl",
}


@dataclass(frozen=True)
class RunArtifacts:
    run_id: str
    base_dir: Path
    run_dir: Path
    research_brief: Path
    research_tasks: Path
    evidence: Path
    verification: Path
    critique: Path
    outline: Path
    draft_report: Path
    final_report: Path
    report_json: Path
    trace: Path

    @classmethod
    def create(cls, base_dir: str | Path, run_id: str) -> "RunArtifacts":
        safe_run_id = _validate_run_id(run_id)
        base_path = Path(base_dir)
        run_dir = base_path / safe_run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        paths = {
            name: run_dir / filename for name, filename in REQUIRED_ARTIFACT_FILES.items()
        }
        return cls(
            run_id=safe_run_id,
            base_dir=base_path,
            run_dir=run_dir,
            **paths,
        )

    def as_dict(self) -> dict[str, Path]:
        return {name: getattr(self, name) for name in REQUIRED_ARTIFACT_FILES}


def _validate_run_id(run_id: str) -> str:
    if not run_id or run_id in {".", ".."}:
        raise ValueError("run_id must be a non-empty path segment")
    candidate = Path(run_id)
    if candidate.name != run_id or candidate.is_absolute():
        raise ValueError("run_id must not contain path separators or traversal")
    return run_id

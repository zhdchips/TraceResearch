"""Seed eval runner for TraceResearch."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from traceresearch.eval.metrics import calculate_case_metrics, summarize_case_results
from traceresearch.evidence.models import EvalResult
from traceresearch.harness.orchestrator import ResearchHarness
from traceresearch.source_discovery.base import ProviderNotConfiguredError
from traceresearch.source_discovery.fixture_provider import FixtureSourceProvider


@dataclass(frozen=True)
class EvalRunResult:
    eval_run_id: str
    result_path: Path
    case_results: list[dict[str, Any]]
    metrics_summary: dict[str, Any]
    case_pass_rate: float
    bad_case_notes: list[str]
    suggested_next_phase: str

    @property
    def failed_case_ids(self) -> list[str]:
        return [
            str(case_result["case_id"])
            for case_result in self.case_results
            if not case_result.get("passed")
        ]


class EvalRunner:
    def __init__(
        self,
        *,
        cases_dir: str | Path = Path("eval/cases"),
        results_dir: str | Path = Path("eval/results"),
        runs_dir: str | Path = Path("runs"),
    ) -> None:
        self.cases_dir = Path(cases_dir)
        self.results_dir = Path(results_dir)
        self.runs_dir = Path(runs_dir)
        self.harness = ResearchHarness()

    def run(self, *, source_provider: str = "fixture") -> EvalRunResult:
        if source_provider != "fixture":
            raise ProviderNotConfiguredError(source_provider)

        eval_run_id = _new_eval_run_id()
        provider = FixtureSourceProvider(cases_dir=self.cases_dir)
        cases = provider.load_eval_cases()
        case_results: list[dict[str, Any]] = []
        bad_case_notes: list[str] = []

        for case in cases.values():
            run_result = self.harness.run_fixture(
                query=case.input_query,
                case_id=case.case_id,
                output_dir=self.runs_dir,
            )
            metric_result = calculate_case_metrics(run_result.artifact_dir, case)
            case_result = {
                "case_id": case.case_id,
                "theme": case.theme,
                "run_id": run_result.run_id,
                "status": run_result.status.value,
                "artifact_dir": str(run_result.artifact_dir),
                "metrics": metric_result["metrics"],
                "pass_fail": metric_result["pass_fail"],
                "passed": metric_result["passed"],
                "bad_case_notes": metric_result["bad_case_notes"],
            }
            case_results.append(case_result)
            if not metric_result["passed"]:
                bad_case_notes.extend(
                    f"{case.case_id}: {note}" for note in metric_result["bad_case_notes"]
                )

        summary = summarize_case_results(case_results)
        suggested_next_phase = "complete" if not bad_case_notes else "eval"
        result_path = self.results_dir / f"{eval_run_id}-summary.json"
        eval_result = EvalResult(
            eval_run_id=eval_run_id,
            created_at=datetime.now(timezone.utc),
            case_results=case_results,
            metrics_summary=summary,
            case_pass_rate=summary["case_pass_rate"],
            bad_case_notes=bad_case_notes,
            suggested_next_phase=suggested_next_phase,
        )
        payload = eval_result.model_dump(mode="json")
        payload["failed_case_ids"] = [
            case_result["case_id"] for case_result in case_results if not case_result["passed"]
        ]
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return EvalRunResult(
            eval_run_id=eval_run_id,
            result_path=result_path,
            case_results=case_results,
            metrics_summary=summary,
            case_pass_rate=summary["case_pass_rate"],
            bad_case_notes=bad_case_notes,
            suggested_next_phase=suggested_next_phase,
        )


def _new_eval_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"eval-{timestamp}-{uuid4().hex[:8]}"

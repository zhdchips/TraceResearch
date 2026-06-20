"""Evaluation metrics for TraceResearch run artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any

from traceresearch.evidence.models import EvalCase, EvidenceStatus
from traceresearch.harness.run_state import RunState

REQUIRED_METRIC_NAMES = (
    "planner_coverage",
    "perspective_diversity",
    "source_relevance",
    "source_authority",
    "citation_completeness",
    "faithfulness",
    "unsupported_claim_count",
    "critical_hallucination_count",
    "case_pass_rate",
)

PASS_THRESHOLDS = {
    "planner_coverage": 1.0,
    "perspective_diversity": 1.0,
    "source_relevance": 0.7,
    "source_authority": 0.7,
    "citation_completeness": 1.0,
    "faithfulness": 1.0,
    "unsupported_claim_count": 0,
    "critical_hallucination_count": 0,
    "case_pass_rate": 1.0,
}


def calculate_case_metrics(run_dir: str | Path, eval_case: EvalCase | None = None) -> dict[str, Any]:
    state = RunState(run_dir)
    evidence = state.evidence()
    verified_evidence = [item for item in evidence if item.status == EvidenceStatus.VERIFIED]
    verified_ids = {item.evidence_id for item in verified_evidence}
    report = _read_json(state.report_paths().report_json)
    brief = _read_json(Path(run_dir) / "research_brief.json")
    verification = _read_json(Path(run_dir) / "verification.json")

    claims = _report_claims(report)
    unsupported_claims = list(report.get("unsupported_claims", []) or [])
    unsupported_claim_count = len(unsupported_claims) + sum(
        1 for claim in claims if claim.get("support_status") == "unsupported"
    )

    claim_evidence_ids = [
        evidence_id
        for claim in claims
        for evidence_id in claim.get("evidence_ids", []) or []
    ]
    citation_completeness = (
        sum(1 for claim in claims if claim.get("evidence_ids")) / len(claims)
        if claims
        else 0.0
    )
    evidence_ids_exist = bool(claim_evidence_ids) and all(
        evidence_id in verified_ids for evidence_id in claim_evidence_ids
    )
    faithfulness = 1.0 if evidence_ids_exist and unsupported_claim_count == 0 else 0.0
    critical_hallucination_count = int(
        verification.get("critical_hallucination_count", 0) or 0
    )
    if unsupported_claim_count or not faithfulness:
        critical_hallucination_count = max(critical_hallucination_count, 1)

    expected_perspectives = eval_case.expected_perspectives if eval_case else []
    planned_perspectives = [str(item) for item in brief.get("perspectives", []) or []]
    planner_coverage = _planner_coverage(planned_perspectives, expected_perspectives)
    perspective_diversity = min(len({item.lower() for item in planned_perspectives}) / 3, 1.0)

    metrics = {
        "planner_coverage": _round(planner_coverage),
        "perspective_diversity": _round(perspective_diversity),
        "source_relevance": _round(_average([item.relevance_score for item in verified_evidence])),
        "source_authority": _round(_average([item.authority_score for item in verified_evidence])),
        "citation_completeness": _round(citation_completeness),
        "faithfulness": faithfulness,
        "unsupported_claim_count": unsupported_claim_count,
        "critical_hallucination_count": critical_hallucination_count,
        "case_pass_rate": 1.0,
    }
    pass_fail = _pass_fail(metrics)
    bad_case_notes = _bad_case_notes(
        run_dir=Path(run_dir),
        metrics=metrics,
        pass_fail=pass_fail,
        verified_evidence_count=len(verified_evidence),
        claim_count=len(claims),
    )

    return {
        "metrics": metrics,
        "pass_fail": pass_fail,
        "passed": all(pass_fail.values()),
        "bad_case_notes": bad_case_notes,
    }


def summarize_case_results(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(case_results)
    passed_cases = sum(1 for item in case_results if item.get("passed"))
    failed_cases = total - passed_cases
    case_pass_rate = passed_cases / total if total else 0.0

    metric_names = sorted(
        {
            metric_name
            for case_result in case_results
            for metric_name in case_result.get("metrics", {})
            if metric_name != "case_pass_rate"
        }
    )
    metric_averages = {
        metric_name: _round(
            mean(float(case_result.get("metrics", {}).get(metric_name, 0.0)) for case_result in case_results)
        )
        for metric_name in metric_names
    }
    metric_averages["case_pass_rate"] = _round(case_pass_rate)

    return {
        "total_cases": total,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "case_pass_rate": _round(case_pass_rate),
        "metric_averages": metric_averages,
    }


def _report_claims(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        claim
        for section in report.get("sections", []) or []
        for claim in section.get("claims", []) or []
    ]


def _planner_coverage(planned_perspectives: list[str], expected_perspectives: list[str]) -> float:
    if not expected_perspectives:
        return 1.0 if planned_perspectives else 0.0

    planned = " ".join(planned_perspectives).lower()
    covered = sum(
        1 for expected in expected_perspectives if expected.lower() in planned
    )
    return covered / len(expected_perspectives)


def _pass_fail(metrics: dict[str, float | int]) -> dict[str, bool]:
    return {
        "planner_coverage": metrics["planner_coverage"] >= PASS_THRESHOLDS["planner_coverage"],
        "perspective_diversity": metrics["perspective_diversity"] >= PASS_THRESHOLDS["perspective_diversity"],
        "source_relevance": metrics["source_relevance"] >= PASS_THRESHOLDS["source_relevance"],
        "source_authority": metrics["source_authority"] >= PASS_THRESHOLDS["source_authority"],
        "citation_completeness": metrics["citation_completeness"] >= PASS_THRESHOLDS["citation_completeness"],
        "faithfulness": metrics["faithfulness"] >= PASS_THRESHOLDS["faithfulness"],
        "unsupported_claim_count": metrics["unsupported_claim_count"] == PASS_THRESHOLDS["unsupported_claim_count"],
        "critical_hallucination_count": metrics["critical_hallucination_count"]
        == PASS_THRESHOLDS["critical_hallucination_count"],
        "case_pass_rate": metrics["case_pass_rate"] >= PASS_THRESHOLDS["case_pass_rate"],
    }


def _bad_case_notes(
    *,
    run_dir: Path,
    metrics: dict[str, float | int],
    pass_fail: dict[str, bool],
    verified_evidence_count: int,
    claim_count: int,
) -> list[str]:
    notes: list[str] = []
    if verified_evidence_count == 0:
        notes.append(f"{run_dir.name}: missing verified evidence in evidence.jsonl.")
    if claim_count == 0:
        notes.append(f"{run_dir.name}: report.json contains no claims to evaluate.")
    if metrics["unsupported_claim_count"]:
        notes.append(f"{run_dir.name}: unsupported claims entered report.json.")
    for metric_name, passed in pass_fail.items():
        if not passed:
            notes.append(f"{run_dir.name}: metric {metric_name} failed with value {metrics[metric_name]}.")
    return notes


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _round(value: float) -> float:
    return round(float(value), 4)

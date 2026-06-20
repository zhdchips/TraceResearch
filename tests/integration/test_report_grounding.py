import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from traceresearch.cli import app


def _run_framework_fixture_case(tmp_path: Path) -> Path:
    output_dir = tmp_path / "runs"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "run",
            "--query",
            "Compare LangGraph, AutoGen, and CrewAI for building research agents",
            "--source-provider",
            "fixture",
            "--case-id",
            "001-framework-comparison",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    run_dirs = [path for path in output_dir.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    return run_dirs[0]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _report_claims(report: dict[str, Any]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for section in report["sections"]:
        claims.extend(section.get("claims", []))
    return claims


def test_final_report_key_claims_reference_verified_evidence(tmp_path: Path) -> None:
    artifact_dir = _run_framework_fixture_case(tmp_path)

    report = json.loads((artifact_dir / "report.json").read_text(encoding="utf-8"))
    final_report = (artifact_dir / "final_report.md").read_text(encoding="utf-8")
    evidence_rows = _read_jsonl(artifact_dir / "evidence.jsonl")
    verified_evidence_ids = {
        row["evidence_id"] for row in evidence_rows if row["status"] == "verified"
    }

    claims = _report_claims(report)
    assert claims
    assert verified_evidence_ids

    for claim in claims:
        evidence_ids = claim.get("evidence_ids", [])
        assert claim["support_status"] != "unsupported"
        assert evidence_ids, f"claim lacks evidence IDs: {claim['claim_id']}"
        assert set(evidence_ids).issubset(verified_evidence_ids)
        for evidence_id in evidence_ids:
            assert f"[{evidence_id}]" in final_report


def test_unsupported_claims_do_not_enter_final_report(tmp_path: Path) -> None:
    artifact_dir = _run_framework_fixture_case(tmp_path)

    report = json.loads((artifact_dir / "report.json").read_text(encoding="utf-8"))
    final_report = (artifact_dir / "final_report.md").read_text(encoding="utf-8")

    for unsupported_claim in report.get("unsupported_claims", []):
        text = unsupported_claim["text"] if isinstance(unsupported_claim, dict) else str(unsupported_claim)
        assert text not in final_report

    assert report["unsupported_claims"] == []
    assert "support_status: unsupported" not in final_report

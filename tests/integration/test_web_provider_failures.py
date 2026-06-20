import json
from pathlib import Path

import pytest

from traceresearch.evidence.models import ResearchTask, SourceDocument, SourceResult
from traceresearch.harness.orchestrator import ResearchHarness
from traceresearch.source_discovery.base import (
    ProviderNoResultsError,
    ProviderRateLimitedError,
    ProviderServiceError,
    ProviderTimeoutError,
    SourceDiscoveryProvider,
    SourceRef,
)


class FailingWebProvider(SourceDiscoveryProvider):
    provider_name = "web"
    provider_display_name = "exa"
    tool_name = "exa.search"

    def __init__(self, error) -> None:
        self.error = error

    def search(self, task: ResearchTask, limit: int) -> list[SourceResult]:
        raise self.error

    def fetch(self, source_ref: SourceRef) -> SourceDocument:  # pragma: no cover
        raise AssertionError("fetch should not be called when search fails")


def _trace_rows(run_dir: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (ProviderTimeoutError("exa", "search", message="network timed out"), "provider_timeout"),
        (ProviderRateLimitedError("exa", "search", status_code=429), "provider_rate_limited"),
        (
            ProviderServiceError(
                "exa",
                "search",
                message="provider returned 502",
                status_code=502,
            ),
            "provider_error",
        ),
        (ProviderNoResultsError("exa"), "provider_no_results"),
    ],
)
def test_web_provider_failures_write_safe_trace_and_failed_run(
    tmp_path: Path,
    error,
    expected_code: str,
) -> None:
    result = ResearchHarness().run(
        query="What changed in AI coding agents during the last 12 months?",
        source_provider=FailingWebProvider(error),
        output_dir=tmp_path / "runs",
    )

    assert result.status.value == "failed"
    assert result.final_report_path is None
    assert (result.artifact_dir / "trace.jsonl").is_file()
    assert (result.artifact_dir / "research_brief.json").is_file()
    assert (result.artifact_dir / "research_tasks.json").is_file()
    assert not (result.artifact_dir / "evidence.jsonl").exists()
    assert not (result.artifact_dir / "final_report.md").exists()
    assert not (result.artifact_dir / "report.json").exists()

    rows = _trace_rows(result.artifact_dir)
    failure_events = [
        row
        for row in rows
        if row["status"] == "failed" and row.get("error", {}).get("type") == expected_code
    ]
    assert failure_events
    assert any(row.get("tool_name") == "exa.search" for row in failure_events)
    assert "unsupported deterministic conclusion" not in "\n".join(
        path.read_text(encoding="utf-8")
        for path in result.artifact_dir.iterdir()
        if path.is_file()
    ).lower()


def test_provider_failure_artifacts_do_not_leak_secret(tmp_path: Path) -> None:
    secret = "exa_live_secret_for_redaction"
    error = ProviderServiceError(
        "exa",
        "search",
        message=f"upstream failed with {secret}",
        status_code=503,
    )

    result = ResearchHarness().run(
        query="What changed in AI coding agents during the last 12 months?",
        source_provider=FailingWebProvider(error),
        output_dir=tmp_path / "runs",
    )

    artifact_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in result.artifact_dir.iterdir()
        if path.is_file()
    )
    assert secret not in artifact_text
    assert secret not in repr(error)

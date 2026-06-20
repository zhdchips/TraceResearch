import json
from datetime import datetime, timezone
from pathlib import Path

from traceresearch.evidence.models import SourceDocument, SourceResult, SourceType
from traceresearch.harness.orchestrator import ResearchHarness
from traceresearch.source_discovery.base import SourceDiscoveryProvider, SourceRef


class FakeWebProvider(SourceDiscoveryProvider):
    provider_name = "web"
    provider_display_name = "exa"

    def search(self, task, limit: int) -> list[SourceResult]:
        return [
            SourceResult(
                source_id="exa:ai-coding-agents",
                provider="web",
                title="AI coding agents report",
                url="https://example.com/ai-coding-agents",
                source_type=SourceType.REPORT,
                publisher="Example Research",
                published_at=None,
                retrieved_at=datetime.now(timezone.utc),
                snippet="AI coding agents increasingly perform delegated engineering tasks.",
                provider_rank=1,
            )
        ]

    def fetch(self, source_ref: SourceRef) -> SourceDocument:
        return SourceDocument(
            source_id=source_ref.source_id,
            title="AI coding agents report",
            url=source_ref.url,
            content_excerpt=(
                "AI coding agents increasingly perform delegated engineering tasks "
                "and require stronger runtime isolation."
            ),
            metadata={
                "provider": "web",
                "provider_name": "exa",
                "authority_score": 0.8,
                "relevance_score": 0.9,
                "key_points": ["Agentic coding tools are moving toward delegated work."],
                "supported_claims": [
                    "AI coding agents increasingly perform delegated engineering tasks."
                ],
                "limitations": ["Mocked provider result for integration testing."],
            },
            retrieved_at=datetime.now(timezone.utc),
        )


def test_mocked_web_run_generates_required_artifacts(tmp_path: Path) -> None:
    result = ResearchHarness().run(
        query="What changed in AI coding agents during the last 12 months?",
        source_provider=FakeWebProvider(),
        output_dir=tmp_path / "runs",
    )

    assert result.status.value == "completed"
    assert result.final_report_path is not None
    for filename in [
        "research_brief.json",
        "research_tasks.json",
        "evidence.jsonl",
        "trace.jsonl",
        "final_report.md",
        "report.json",
    ]:
        assert (result.artifact_dir / filename).is_file()


def test_mocked_web_run_report_is_grounded_and_traceable(tmp_path: Path) -> None:
    result = ResearchHarness().run(
        query="What changed in AI coding agents during the last 12 months?",
        source_provider=FakeWebProvider(),
        output_dir=tmp_path / "runs",
    )

    final_report = (result.artifact_dir / "final_report.md").read_text(encoding="utf-8")
    evidence_rows = [
        json.loads(line)
        for line in (result.artifact_dir / "evidence.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    trace_rows = [
        json.loads(line)
        for line in (result.artifact_dir / "trace.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]

    assert "[EV-" in final_report
    assert evidence_rows
    assert evidence_rows[0]["source"]["provider"] == "web"
    assert evidence_rows[0]["source"]["title"] == "AI coding agents report"
    assert evidence_rows[0]["source"]["url"] == "https://example.com/ai-coding-agents"
    assert evidence_rows[0]["source"]["retrieved_at"]
    assert any(row.get("tool_name") in {"exa.search", "web_search"} for row in trace_rows)

from pathlib import Path

from typer.testing import CliRunner

from traceresearch.cli import app


def test_cli_web_without_key_returns_not_configured_and_no_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRACERESEARCH_WEB_PROVIDER", "exa")
    monkeypatch.delenv("EXA_API_KEY", raising=False)

    result = CliRunner().invoke(
        app,
        [
            "run",
            "--query",
            "What changed in AI coding agents during the last 12 months?",
            "--source-provider",
            "web",
            "--output-dir",
            str(tmp_path / "runs"),
        ],
    )

    assert result.exit_code != 0
    assert "status=failed" in result.output
    assert "error_type=provider_not_configured" in result.output
    assert "fixture" not in result.output.lower()
    assert not list((tmp_path / "runs").glob("*/evidence.jsonl"))


def test_cli_web_configured_success_uses_provider_factory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from traceresearch.source_discovery.exa_provider import ExaSearchProvider

    monkeypatch.setenv("TRACERESEARCH_WEB_PROVIDER", "exa")
    monkeypatch.setenv("EXA_API_KEY", "test-exa-secret")
    monkeypatch.setattr(
        ExaSearchProvider,
        "_post_search",
        lambda _self, _body: {
            "requestId": "exa-request-123",
            "results": [
                {
                    "id": "result-1",
                    "title": "AI coding agents report",
                    "url": "https://example.com/ai-coding-agents",
                    "highlights": ["AI coding agents increasingly perform delegated tasks."],
                    "summary": "AI coding agents moved toward delegated work.",
                }
            ],
        },
    )

    result = CliRunner().invoke(
        app,
        [
            "run",
            "--query",
            "What changed in AI coding agents during the last 12 months?",
            "--source-provider",
            "web",
            "--output-dir",
            str(tmp_path / "runs"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "run_id=" in result.output
    assert "status=completed" in result.output
    assert "artifact_dir=" in result.output
    assert "provider_not_configured" not in result.output

from pathlib import Path

from typer.testing import CliRunner

from traceresearch.cli import app


def _run_web(tmp_path: Path) -> object:
    return CliRunner().invoke(
        app,
        [
            "run",
            "--query",
            "What changed in AI coding agents during the last 12 months?",
            "--source-provider",
            "web",
            "--case-id",
            "001-framework-comparison",
            "--output-dir",
            str(tmp_path / "runs"),
        ],
    )


def test_web_without_exa_key_fails_without_fixture_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRACERESEARCH_WEB_PROVIDER", "exa")
    monkeypatch.delenv("EXA_API_KEY", raising=False)

    result = _run_web(tmp_path)

    assert result.exit_code != 0
    assert "status=failed" in result.output
    assert "error_type=provider_not_configured" in result.output
    assert "fixture" not in result.output.lower()
    assert not list((tmp_path / "runs").glob("*/evidence.jsonl"))
    assert not list((tmp_path / "runs").glob("*/final_report.md"))


def test_web_with_blank_exa_key_fails_without_fixture_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRACERESEARCH_WEB_PROVIDER", "exa")
    monkeypatch.setenv("EXA_API_KEY", "   ")

    result = _run_web(tmp_path)

    assert result.exit_code != 0
    assert "status=failed" in result.output
    assert "error_type=provider_not_configured" in result.output
    assert "fixture" not in result.output.lower()
    assert not list((tmp_path / "runs").glob("*/evidence.jsonl"))


def test_unconfigured_web_error_does_not_leak_fake_secret(
    tmp_path: Path,
    monkeypatch,
) -> None:
    secret = "exa_live_secret_for_redaction"
    monkeypatch.setenv("TRACERESEARCH_WEB_PROVIDER", "unsupported-live-provider")
    monkeypatch.setenv("EXA_API_KEY", secret)

    result = _run_web(tmp_path)

    assert result.exit_code != 0
    assert "status=failed" in result.output
    assert secret not in result.output
    assert "fixture" not in result.output.lower()

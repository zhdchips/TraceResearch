"""CLI entrypoint for TraceResearch."""

import json
from pathlib import Path

import typer

from traceresearch.eval.llm_smoke import LLMSmokeRunner
from traceresearch.eval.runner import EvalRunner
from traceresearch.harness.mode_factory import resolve_mode
from traceresearch.harness.orchestrator import ResearchHarness
from traceresearch.llm.config import LLMProviderConfig
from traceresearch.llm.deepseek_provider import DeepSeekProvider
from traceresearch.source_discovery.base import ProviderNotConfiguredError, SourceDiscoveryError
from traceresearch.source_discovery.factory import build_source_provider

app = typer.Typer(help="TraceResearch Deep Research CLI.")


@app.callback()
def main() -> None:
    """TraceResearch Deep Research CLI."""


@app.command("run")
def run(
    query: str = typer.Option(..., "--query", help="Research question to investigate."),
    source_provider: str = typer.Option(
        "fixture",
        "--source-provider",
        help="Source provider to use. MVP supports fixture; web returns not configured.",
    ),
    case_id: str | None = typer.Option(
        None,
        "--case-id",
        help="Fixture eval case ID.",
    ),
    output_dir: Path = typer.Option(
        Path("runs"),
        "--output-dir",
        help="Parent directory for run artifacts.",
    ),
    writer_mode: str = typer.Option(
        "deterministic",
        "--writer-mode",
        help="Writer mode: 'deterministic' (default) or 'llm'.",
    ),
    verifier_mode: str = typer.Option(
        "deterministic",
        "--verifier-mode",
        help="Verifier mode: 'deterministic' (default) or 'llm'.",
    ),
) -> None:
    try:
        provider = build_source_provider(source_provider=source_provider, case_id=case_id)
    except SourceDiscoveryError as error:
        typer.echo(f"status=failed")
        typer.echo(f"error_type={error.code}")
        typer.echo(f"error_message={error}")
        raise typer.Exit(code=1)

    # Resolve Writer/Verifier modes (env var can override default CLI values)
    resolved_writer = resolve_mode(writer_mode, "WRITER")
    resolved_verifier = resolve_mode(verifier_mode, "VERIFIER")

    # Build LLM provider if configured
    llm_provider = None
    llm_config = LLMProviderConfig.from_env()
    if llm_config.is_configured():
        llm_provider = DeepSeekProvider(
            api_key=llm_config.api_key,
            model=llm_config.model,
            base_url=llm_config.base_url,
            timeout_seconds=llm_config.timeout_seconds,
            max_tokens=llm_config.max_tokens,
            temperature=llm_config.temperature,
        )

    try:
        if source_provider == "fixture":
            result = ResearchHarness(
                writer_mode=resolved_writer,
                verifier_mode=resolved_verifier,
                llm_provider=llm_provider,
            ).run_fixture(
                query=query,
                case_id=case_id,
                output_dir=output_dir,
            )
        else:
            result = ResearchHarness(
                writer_mode=resolved_writer,
                verifier_mode=resolved_verifier,
                llm_provider=llm_provider,
            ).run(
                query=query,
                source_provider=provider,
                output_dir=output_dir,
            )
    except SourceDiscoveryError as error:
        typer.echo("status=failed")
        typer.echo(f"error_type={error.code}")
        typer.echo(f"error_message={error}")
        raise typer.Exit(code=1)
    typer.echo(f"run_id={result.run_id}")
    typer.echo(f"status={result.status.value}")
    typer.echo(f"artifact_dir={result.artifact_dir}")
    if result.status.value == "failed":
        raise typer.Exit(code=1)


@app.command("eval")
def eval_command(
    cases_dir: Path = typer.Option(
        Path("eval/cases"),
        "--cases-dir",
        help="Directory containing eval case YAML files.",
    ),
    source_provider: str = typer.Option(
        "fixture",
        "--source-provider",
        help="Source provider to use. MVP supports fixture.",
    ),
    results_dir: Path = typer.Option(
        Path("eval/results"),
        "--results-dir",
        help="Directory for eval summary JSON artifacts.",
    ),
    runs_dir: Path = typer.Option(
        Path("runs"),
        "--runs-dir",
        help="Parent directory for per-case run artifacts.",
    ),
) -> None:
    if source_provider != "fixture":
        error = ProviderNotConfiguredError(source_provider)
        typer.echo("status=failed")
        typer.echo(f"error_type={error.code}")
        typer.echo(f"error_message={error}")
        raise typer.Exit(code=1)

    result = EvalRunner(
        cases_dir=cases_dir,
        results_dir=results_dir,
        runs_dir=runs_dir,
    ).run(source_provider=source_provider)
    failed_case_ids = ",".join(result.failed_case_ids) if result.failed_case_ids else "none"
    typer.echo(f"eval_run_id={result.eval_run_id}")
    typer.echo(f"case_pass_rate={result.case_pass_rate:.2f}")
    typer.echo(f"failed_case_ids={failed_case_ids}")
    typer.echo(f"suggested_next_phase={result.suggested_next_phase}")
    typer.echo(f"result_file={result.result_path}")


@app.command("llm-smoke")
def llm_smoke_command(
    cases_dir: Path = typer.Option(
        Path("eval/llm_smoke_cases"),
        "--cases-dir",
        help="Directory containing LLM smoke case YAML files.",
    ),
    results_dir: Path = typer.Option(
        Path("eval/results"),
        "--results-dir",
        help="Directory for smoke eval summary JSON.",
    ),
) -> None:
    """Run LLM smoke eval (manual only — requires LLM credentials)."""
    llm_config = LLMProviderConfig.from_env()
    if not llm_config.is_configured():
        typer.echo("LLM not configured — running with deterministic baseline.")
        typer.echo("Set TRACERESEARCH_LLM_API_KEY or DEEPSEEK_API_KEY to enable LLM mode.")
        runner = LLMSmokeRunner(cases_dir=cases_dir, results_dir=results_dir)
    else:
        provider = DeepSeekProvider(
            api_key=llm_config.api_key,
            model=llm_config.model,
            base_url=llm_config.base_url,
            timeout_seconds=llm_config.timeout_seconds,
            max_tokens=llm_config.max_tokens,
            temperature=llm_config.temperature,
        )
        runner = LLMSmokeRunner(
            cases_dir=cases_dir, results_dir=results_dir, llm_provider=provider
        )

    summary = runner.run()
    typer.echo(f"eval_run_id={summary['eval_run_id']}")
    typer.echo(f"case_pass_rate={summary['case_pass_rate']:.2f}")
    typer.echo(f"total_cases={summary['total_cases']}")
    typer.echo(f"passed_cases={summary['passed_cases']}")

    result_path = results_dir / f"{summary['eval_run_id']}-summary.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    typer.echo(f"result_file={result_path}")

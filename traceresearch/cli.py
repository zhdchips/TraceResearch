"""CLI entrypoint for TraceResearch."""

from pathlib import Path

import typer

from traceresearch.eval.runner import EvalRunner
from traceresearch.harness.orchestrator import ResearchHarness
from traceresearch.source_discovery.base import ProviderNotConfiguredError
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
) -> None:
    if source_provider != "fixture":
        error = ProviderNotConfiguredError(source_provider)
        typer.echo(f"status=failed")
        typer.echo(f"error_type={error.code}")
        typer.echo(f"error_message={error}")
        raise typer.Exit(code=1)

    build_source_provider(source_provider="fixture", case_id=case_id)
    result = ResearchHarness().run_fixture(
        query=query,
        case_id=case_id,
        output_dir=output_dir,
    )
    typer.echo(f"run_id={result.run_id}")
    typer.echo(f"status={result.status.value}")
    typer.echo(f"artifact_dir={result.artifact_dir}")


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

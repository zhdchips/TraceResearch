"""CLI entrypoint for TraceResearch."""

from pathlib import Path

import typer

from traceresearch.harness.orchestrator import ResearchHarness
from traceresearch.source_discovery.base import ProviderNotConfiguredError

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

    result = ResearchHarness().run_fixture(
        query=query,
        case_id=case_id,
        output_dir=output_dir,
    )
    typer.echo(f"run_id={result.run_id}")
    typer.echo(f"status={result.status.value}")
    typer.echo(f"artifact_dir={result.artifact_dir}")

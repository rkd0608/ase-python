"""Public example-matrix CLI commands."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from ase.errors import CLIError
from ase.examples_matrix import run_examples

app = typer.Typer(help="Run ASE's public example matrix.")
_console = Console()


@app.command("run")
def run(
    example: Annotated[
        list[str] | None,
        typer.Option("--example", help="Run only the named example(s)."),
    ] = None,
) -> None:
    """Run the supported example matrix with the same commands users run."""
    try:
        results = run_examples(example)
    except CLIError as exc:
        _console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    for result in results:
        status = "[green]passed[/green]" if result.passed else "[red]failed[/red]"
        _console.print(f"{result.example_name}: {status}")

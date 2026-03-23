"""Adapter protocol CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ase.adapters.protocol import read_and_verify
from ase.errors import AdapterProtocolError

app = typer.Typer(help="Validate ASE adapter event streams.")
_console = Console()


@app.command("verify")
def verify(
    event_file: Annotated[Path, typer.Argument(help="JSONL adapter event file to validate.")],
) -> None:
    """Validate an adapter event file and print its event-family counts."""
    try:
        _events, result = read_and_verify(event_file)
    except AdapterProtocolError as exc:
        _console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    _console.print(f"events: {result.total_events}")
    for event_type, count in sorted(result.event_type_counts.items()):
        _console.print(f"  {event_type}: {count}")
    for warning in result.warnings:
        _console.print(f"[yellow]{warning}[/yellow]")
    if result.passed:
        _console.print("[green]adapter event stream passed[/green]")
        return
    for error in result.errors:
        _console.print(f"[red]{error}[/red]")
    raise typer.Exit(code=1)

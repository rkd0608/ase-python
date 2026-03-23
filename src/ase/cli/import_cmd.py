"""ase import — convert external trace formats into native ASE traces."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ase.cli._trace_outputs import write_trace_artifacts
from ase.config.model import OutputFormat
from ase.trace.otel_import import read_otel_trace

app = typer.Typer(help="Import external trace formats into native ASE traces.")
_console = Console()


@app.command("otel")
def otel(
    trace_file: Annotated[Path, typer.Argument(help="OTEL-like JSON trace file.")],
    trace_out: Annotated[
        Path | None,
        typer.Option("--trace-out", help="Write native trace JSON here."),
    ] = None,
    output: Annotated[OutputFormat | None, typer.Option("--output", "-o")] = None,
    out_file: Annotated[Path | None, typer.Option("--out-file", "-f")] = None,
) -> None:
    """Import one OTEL-like JSON trace into native ASE format."""
    trace = read_otel_trace(trace_file)
    write_trace_artifacts(trace, trace_out=trace_out, output=output, out_file=out_file)
    _console.print(f"trace_id: {trace.trace_id}")
    if trace_out is not None:
        _console.print(f"trace_out: {trace_out}")

"""ase replay — convert adapter events into native ASE traces."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ase.adapters.protocol import read_and_verify
from ase.adapters.replay import trace_from_adapter_events
from ase.cli._trace_outputs import write_trace_artifacts
from ase.config.model import OutputFormat
from ase.errors import AdapterProtocolError

_console = Console()


def run(
    event_file: Annotated[Path, typer.Argument(help="JSONL adapter event file.")],
    scenario_id: Annotated[
        str,
        typer.Option("--scenario-id", help="Scenario id for the replayed trace."),
    ],
    scenario_name: Annotated[
        str,
        typer.Option(
            "--scenario-name",
            help="Scenario name for the replayed trace.",
        ),
    ],
    trace_out: Annotated[
        Path | None,
        typer.Option("--trace-out", help="Write native trace JSON here."),
    ] = None,
    output: Annotated[OutputFormat | None, typer.Option("--output", "-o")] = None,
    out_file: Annotated[Path | None, typer.Option("--out-file", "-f")] = None,
) -> None:
    """Replay one validated adapter event stream into a native ASE trace."""
    events, result = read_and_verify(event_file)
    if not result.passed:
        raise AdapterProtocolError("adapter event stream failed verification")
    trace = trace_from_adapter_events(events, scenario_id, scenario_name)
    write_trace_artifacts(trace, trace_out=trace_out, output=output, out_file=out_file)
    _console.print(f"trace_id: {trace.trace_id}")
    if trace_out is not None:
        _console.print(f"trace_out: {trace_out}")

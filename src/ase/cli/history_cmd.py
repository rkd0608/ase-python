"""ase history — list and inspect stored trace runs."""

from __future__ import annotations

import asyncio
import datetime
from typing import Annotated

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from ase.storage.trace_store import TraceStore
from ase.trace.model import Trace

_console = Console()


def run(
    scenario: Annotated[str | None, typer.Option("--scenario", "-s")] = None,
    status: Annotated[str | None, typer.Option("--status")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n")] = 20,
    trace_id: Annotated[str | None, typer.Option("--trace-id")] = None,
) -> None:
    """List or inspect stored trace runs from the persistent trace store."""
    asyncio.run(_run(scenario, status, limit, trace_id))


async def _run(
    scenario: str | None,
    status: str | None,
    limit: int,
    trace_id: str | None,
) -> None:
    store = TraceStore()
    await store.setup()
    if trace_id:
        await _show_trace(store, trace_id)
    else:
        await _list_traces(store, scenario, status, limit)
    await store.close()


async def _show_trace(store: TraceStore, trace_id: str) -> None:
    """Fetch and display one trace with runtime and evaluation metadata."""
    trace = await store.get_trace(trace_id)
    if trace is None:
        _console.print(f"[red]Trace not found: {trace_id}[/red]")
        raise typer.Exit(code=1)
    _console.print(f"\n[bold]Run:[/bold] {trace.trace_id}")
    _console.print(f"Scenario: {trace.scenario_id} — {trace.scenario_name}")
    _console.print(f"Run result: [bold]{trace.status.value}[/bold]")
    _console.print(f"Checks: [bold]{_evaluation_status(trace)}[/bold]")
    _console.print(f"Run type:   [bold]{_runtime_mode(trace)}[/bold]")
    _console.print(f"Framework:  [bold]{_framework_label(trace)}[/bold]")
    if trace.certification_level is not None:
        _console.print(f"Certified:  {trace.certification_level.value}")
    if trace.evaluation is not None:
        _console.print(f"ASE Score:  {trace.evaluation.ase_score:.2f}")
    _console.print(f"Duration:   {trace.metrics.total_duration_ms:.0f}ms")
    _console.print(f"Tool calls: {trace.metrics.total_tool_calls}")
    if trace.error_message:
        _console.print(f"\n[red]Main reason:[/red] {trace.error_message}")
    _console.print("\n[bold]What happened:[/bold]")
    for item in _what_happened(trace):
        _console.print(f"- {item}")
    if trace.stderr_output:
        _console.print(f"\n[yellow]Stderr:[/yellow]\n{trace.stderr_output}")


async def _list_traces(
    store: TraceStore,
    scenario: str | None,
    status: str | None,
    limit: int,
) -> None:
    """Display a summary table of recent runs."""
    rows = await store.list_traces(scenario_id=scenario, status=status, limit=limit)
    if not rows:
        _console.print("[yellow]No traces found.[/yellow]")
        return
    table = Table(title="Trace History", box=box.SIMPLE_HEAD, expand=False)
    table.add_column("Run ID", style="dim", no_wrap=True)
    table.add_column("Scenario", style="bold")
    table.add_column("Run type")
    table.add_column("Framework")
    table.add_column("Checks")
    table.add_column("Run result")
    table.add_column("Certified")
    table.add_column("Score", justify="right")
    table.add_column("Started At")
    for row in rows:
        score = row["ase_score"]
        table.add_row(
            row["trace_id"][:26],
            row["scenario_id"],
            row.get("runtime_mode") or "unknown",
            row.get("framework") or "unknown",
            row["evaluation_status"] or "unknown",
            row["status"],
            row.get("certification_level") or "—",
            f"{score:.2f}" if score is not None else "—",
            _ms_to_str(row["started_at_ms"]),
        )
    _console.print()
    _console.print(table)
    _console.print(f"\n[dim]Showing {len(rows)} of last {limit} runs.[/dim]\n")


def _ms_to_str(ms: float | None) -> str:
    """Render millisecond timestamps as local human-readable strings."""
    if ms is None:
        return "—"
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def _evaluation_status(trace: Trace) -> str:
    """Return a human-readable evaluation outcome for a trace."""
    if trace.evaluation is None:
        return "unknown"
    return "passed" if trace.evaluation.passed else "failed"


def _runtime_mode(trace: Trace) -> str:
    """Return the high-level run type for a stored trace."""
    if trace.runtime_provenance is None:
        return "unknown"
    return trace.runtime_provenance.mode


def _framework_label(trace: Trace) -> str:
    """Return the framework name for a stored trace."""
    if trace.runtime_provenance is None:
        return "unknown"
    return trace.runtime_provenance.framework or "unknown"


def _what_happened(trace: Trace) -> list[str]:
    """Build a short plain-language summary for one stored run."""
    items = []
    if trace.status.value == "passed":
        items.append("The agent run completed successfully.")
    else:
        items.append(f"The agent run ended with status '{trace.status.value}'.")
    if trace.evaluation is None:
        items.append("Checks are not attached to this run.")
    elif trace.evaluation.passed:
        items.append("Checks passed.")
    else:
        items.append("Checks failed.")
    return items

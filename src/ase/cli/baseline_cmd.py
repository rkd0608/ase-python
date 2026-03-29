"""ase baseline - pin, inspect, list, and clear regression baselines."""

from __future__ import annotations

import asyncio
import datetime
from typing import Annotated

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from ase.errors import TraceSerializationError
from ase.storage.trace_store import TraceStore

_console = Console()

app = typer.Typer(help="Pin and inspect ASE baselines.", no_args_is_help=True)


@app.command("set")
def set_baseline(
    scenario_arg: Annotated[
        str | None,
        typer.Argument(help="Scenario id to pin.", show_default=False),
    ] = None,
    trace_id_arg: Annotated[
        str | None,
        typer.Argument(help="Trace id to pin as the baseline.", show_default=False),
    ] = None,
    scenario: Annotated[
        str | None,
        typer.Option("--scenario", "-s", help="Scenario id to pin."),
    ] = None,
    trace_id: Annotated[
        str | None,
        typer.Option("--trace-id", help="Trace id to pin as the baseline."),
    ] = None,
) -> None:
    """Pin one stored run as the baseline for a scenario."""
    resolved_scenario = _require_value(scenario_arg, scenario, "scenario")
    resolved_trace_id = _require_value(trace_id_arg, trace_id, "trace-id")
    asyncio.run(_set_baseline(resolved_scenario, resolved_trace_id))


@app.command("get")
def get_baseline(
    scenario_arg: Annotated[
        str | None,
        typer.Argument(help="Scenario id to inspect.", show_default=False),
    ] = None,
    scenario: Annotated[
        str | None,
        typer.Option("--scenario", "-s", help="Scenario id to inspect."),
    ] = None,
) -> None:
    """Show the currently pinned baseline for one scenario."""
    asyncio.run(_get_baseline(_require_value(scenario_arg, scenario, "scenario")))


@app.command("list")
def list_baselines(
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max baselines to show.")] = 20,
) -> None:
    """List pinned baselines."""
    asyncio.run(_list_baselines(limit))


@app.command("clear")
def clear_baseline(
    scenario_arg: Annotated[
        str | None,
        typer.Argument(help="Scenario id to clear.", show_default=False),
    ] = None,
    scenario: Annotated[
        str | None,
        typer.Option("--scenario", "-s", help="Scenario id to clear."),
    ] = None,
    clear_all: Annotated[
        bool,
        typer.Option("--all", help="Clear all pinned baselines."),
    ] = False,
) -> None:
    """Remove one pinned baseline or all of them."""
    resolved_scenario = scenario_arg or scenario
    if resolved_scenario and clear_all:
        _console.print("[red]choose either --scenario or --all, not both[/red]")
        raise typer.Exit(code=1)
    if not resolved_scenario and not clear_all:
        _console.print("[red]provide --scenario or --all[/red]")
        raise typer.Exit(code=1)
    asyncio.run(_clear_baseline(resolved_scenario if resolved_scenario else None))


async def _set_baseline(scenario_id: str, trace_id: str) -> None:
    store = TraceStore()
    await store.setup()
    try:
        row = await store.set_baseline(scenario_id, trace_id)
    except TraceSerializationError as exc:
        _console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    finally:
        await store.close()
    _console.print(f"Baseline set for {row['scenario_id']}: {row['trace_id']}")
    _console.print(f"  Run result: {row['run_result']}")
    _console.print(f"  Checks:     {row.get('evaluation_status') or 'unknown'}")
    _console.print(f"  Framework:  {row.get('framework') or 'unknown'}")
    score = row.get("ase_score")
    _console.print(f"  ASE score:  {score if score is not None else '—'}")


async def _get_baseline(scenario_id: str) -> None:
    store = TraceStore()
    await store.setup()
    row = await store.get_baseline(scenario_id)
    if row is None:
        await store.close()
        _console.print(f"[yellow]No baseline pinned for scenario: {scenario_id}[/yellow]")
        raise typer.Exit(code=1)
    trace = await store.get_trace(row["trace_id"])
    await store.close()
    _console.print(f"\n[bold]Scenario:[/bold] {row['scenario_id']}")
    _console.print(f"Trace ID:   {row['trace_id']}")
    _console.print(f"Run result: {row['run_result']}")
    _console.print(f"Checks:     {row.get('evaluation_status') or 'unknown'}")
    _console.print(f"Framework:  {row.get('framework') or 'unknown'}")
    if row.get("ase_score") is not None:
        _console.print(f"ASE score:  {float(row['ase_score']):.2f}")
    _console.print(f"Created at: {_ms_to_str(row.get('created_at_ms'))}")
    if trace is not None and trace.error_message:
        _console.print(f"Main reason: {trace.error_message}")


async def _list_baselines(limit: int) -> None:
    store = TraceStore()
    await store.setup()
    rows = await store.list_baselines(limit=limit)
    await store.close()
    if not rows:
        _console.print("[yellow]No baselines found.[/yellow]")
        return
    table = Table(title="ASE Baselines", box=box.SIMPLE_HEAD, expand=False)
    table.add_column("Scenario", style="bold")
    table.add_column("Trace ID", style="dim", no_wrap=True)
    table.add_column("Run result")
    table.add_column("Checks")
    table.add_column("Framework")
    table.add_column("ASE score", justify="right")
    table.add_column("Created At")
    for row in rows:
        score = row.get("ase_score")
        table.add_row(
            row["scenario_id"],
            row["trace_id"],
            row["run_result"],
            row.get("evaluation_status") or "unknown",
            row.get("framework") or "unknown",
            f"{float(score):.2f}" if score is not None else "—",
            _ms_to_str(row.get("created_at_ms")),
        )
    _console.print()
    _console.print(table)


async def _clear_baseline(scenario_id: str | None) -> None:
    store = TraceStore()
    await store.setup()
    removed = await store.clear_baselines(scenario_id=scenario_id)
    await store.close()
    if scenario_id:
        _console.print(f"Removed {removed} baseline(s) for {scenario_id}.")
    else:
        _console.print(f"Removed {removed} baseline(s).")


def _ms_to_str(ms: float | None) -> str:
    """Render millisecond timestamps as local human-readable strings."""
    if ms is None:
        return "—"
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def _require_value(arg_value: str | None, option_value: str | None, label: str) -> str:
    """Accept either positional or option input while keeping old command forms valid."""
    resolved = arg_value or option_value
    if resolved is None:
        _console.print(f"[red]missing required value: {label}[/red]")
        raise typer.Exit(code=1)
    return resolved

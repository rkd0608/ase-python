"""ase watch — run an agent through ASE's proxy and surface observed tool calls."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from ase.core.engine import SimulationEngine
from ase.errors import CLIError
from ase.scenario.model import AgentConfig, EnvironmentConfig, EnvironmentKind, ScenarioConfig
from ase.trace.model import Trace

_console = Console()


def run(
    ctx: typer.Context,
    command: Annotated[list[str] | None, typer.Argument()] = None,
    port: Annotated[int, typer.Option("--port", "-p")] = 0,
    timeout: Annotated[int, typer.Option("--timeout", "-t")] = 120,
) -> None:
    """Execute one command through the proxy-mode runtime with no scenario file."""
    try:
        resolved_command = list(command or ctx.args)
        if not resolved_command:
            raise CLIError("provide an agent command after `--`")
        trace = _run_watch_command(resolved_command, timeout_seconds=timeout, port=port)
        _console.print(f"trace_id: {trace.trace_id}")
        _console.print(f"status: {trace.status.value}")
        _console.print(f"tool_calls: {trace.metrics.total_tool_calls}")
    except CLIError as exc:
        _console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


def _run_watch_command(
    command: list[str],
    *,
    timeout_seconds: int,
    port: int,
) -> Trace:
    """Run the command through the real proxy execution path used by scenarios."""
    import asyncio

    scenario = ScenarioConfig(
        scenario_id="watch-session",
        name="Watch Session",
        agent=AgentConfig(command=command, timeout_seconds=timeout_seconds),
        environment=EnvironmentConfig(kind=EnvironmentKind.REAL),
    )
    result = asyncio.run(SimulationEngine(proxy_port=port).run(scenario))
    if result.trace.status.value == "error":
        raise CLIError(result.trace.error_message or "watch run failed")
    return result.trace

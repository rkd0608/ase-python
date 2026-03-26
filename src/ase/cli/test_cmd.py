"""ase test — run adapter-backed scenarios through ASE's evaluation flow."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ase.adapters.protocol import read_and_verify
from ase.adapters.replay import trace_from_adapter_events
from ase.config.model import OutputFormat
from ase.errors import CLIError
from ase.evaluation.engine import EvaluationEngine
from ase.evaluation.trace_summary import attach_summary
from ase.reporting.terminal import render_suite_header
from ase.scenario.model import AgentRuntimeMode, ScenarioConfig
from ase.scenario.parser import parse_file
from ase.storage.trace_store import TraceStore
from ase.trace.model import TraceStatus

_console = Console()


def run(
    scenario: Annotated[list[Path] | None, typer.Argument()] = None,
    config: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    output: Annotated[OutputFormat | None, typer.Option("--output", "-o")] = None,
    out_file: Annotated[Path | None, typer.Option("--out-file", "-f")] = None,
    fail_fast: Annotated[bool, typer.Option("--fail-fast")] = False,
    tags: Annotated[list[str] | None, typer.Option("--tag")] = None,
    workers: Annotated[int, typer.Option("--workers", "-w")] = 4,
    debug: Annotated[bool, typer.Option("--debug")] = False,
) -> None:
    """Run adapter-backed scenarios through replay, evaluation, and persistence."""
    del config, output, out_file, workers, debug
    scenario_paths = scenario or []
    if not scenario_paths:
        raise typer.Exit(code=1)
    discovered = _collect_scenario_paths(scenario_paths)
    filtered = _filter_by_tags(discovered, tags or [])
    _console.print(
        render_suite_header(
            roots=scenario_paths,
            selected_count=len(filtered),
            total_count=len(discovered),
            tags=tags or [],
        )
    )
    if tags and not filtered:
        _console.print(f"[yellow]warning:[/yellow] no scenarios matched tags: {', '.join(tags)}")
        return
    store = TraceStore()
    _run_all(filtered, store, fail_fast=fail_fast)


def _run_all(paths: list[Path], store: TraceStore, *, fail_fast: bool) -> None:
    """Execute all requested scenarios and stop early only when requested."""
    import asyncio

    asyncio.run(store.setup())
    failures = 0
    for path in paths:
        try:
            _run_one(path, store)
        except CLIError as exc:
            failures += 1
            _console.print(f"[red]{exc}[/red]")
            if fail_fast:
                break
    asyncio.run(store.close())
    if failures:
        raise typer.Exit(code=1)


def _run_one(path: Path, store: TraceStore) -> None:
    """Execute one adapter scenario end to end and persist its trace."""
    scenario = parse_file(path)
    if scenario.runtime_mode != AgentRuntimeMode.ADAPTER:
        raise CLIError(f"recovered ase test currently supports adapter mode only: {path}")
    event_path = _event_path(path, scenario)
    result = _run_agent(scenario, event_path)
    events, verification = read_and_verify(event_path)
    if not verification.passed:
        details = ", ".join(verification.errors)
        raise CLIError(f"adapter event stream failed verification: {details}")
    trace = trace_from_adapter_events(events, scenario.scenario_id, scenario.name)
    trace.stderr_output = result.stderr.strip() or None
    if result.returncode != 0:
        trace.status = TraceStatus.FAILED
        trace.error_message = trace.stderr_output or f"agent exited with code {result.returncode}"
    evaluators = list(scenario.assertions) + list(scenario.policies)
    summary = EvaluationEngine().evaluate(trace, evaluators, {})
    attach_summary(trace, summary)
    import asyncio

    asyncio.run(store.save_trace(trace, ase_score=summary.ase_score))
    _render_summary(trace, summary)
    if not summary.passed or result.returncode != 0:
        raise CLIError(f"scenario failed: {scenario.scenario_id}")


def _collect_scenario_paths(paths: list[Path]) -> list[Path]:
    """Expand file and directory inputs into deterministic scenario file paths."""
    collected: list[Path] = []
    for path in paths:
        if path.is_dir():
            collected.extend(sorted(path.rglob("*.yaml")))
            collected.extend(sorted(path.rglob("*.yml")))
            continue
        collected.append(path)
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in collected:
        try:
            parse_file(path)
        except Exception:
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def _filter_by_tags(paths: list[Path], tags: list[str]) -> list[Path]:
    """Filter scenarios using OR matching across configured tags."""
    if not tags:
        return paths
    requested = {tag.strip() for tag in tags if tag.strip()}
    filtered: list[Path] = []
    for path in paths:
        scenario = parse_file(path)
        if requested.intersection(set(scenario.tags)):
            filtered.append(path)
    return filtered


def _run_agent(scenario: ScenarioConfig, event_path: Path) -> subprocess.CompletedProcess[str]:
    """Run the scenario agent with the event sink path exported to the process."""
    event_path.unlink(missing_ok=True)
    env = dict(scenario.agent.env)
    env.update({"ASE_ADAPTER_EVENT_SOURCE": str(event_path)})
    return subprocess.run(
        scenario.agent.command,
        cwd=Path.cwd(),
        env={**dict(__import__("os").environ), **env},
        capture_output=True,
        text=True,
        check=False,
    )


def _event_path(path: Path, scenario: ScenarioConfig) -> Path:
    """Resolve an adapter event file relative to the scenario file location."""
    runtime = scenario.agent_runtime
    if runtime is None or not runtime.event_source:
        raise CLIError(f"adapter runtime missing event_source: {path}")
    source = Path(runtime.event_source)
    return source if source.is_absolute() else path.resolve().parent / source


def _render_summary(trace: object, summary: object) -> None:
    """Print a compact operator-facing outcome for the recovered test path."""
    trace_id = getattr(trace, "trace_id", "unknown")
    scenario_id = getattr(trace, "scenario_id", "unknown")
    passed = getattr(summary, "passed", False)
    score = getattr(summary, "ase_score", 0.0)
    status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
    _console.print(f"{status} {scenario_id} trace={trace_id} ase_score={score:.2f}")

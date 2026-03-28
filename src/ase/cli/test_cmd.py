"""ase test — run scenarios through ASE's execution and evaluation flow."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ase.config.model import OutputFormat
from ase.core.engine import SimulationEngine
from ase.errors import ASEError, CLIError
from ase.evaluation.engine import EvaluationEngine
from ase.evaluation.trace_summary import attach_summary
from ase.reporting.terminal import render_suite_header
from ase.scenario.model import AssertionConfig, PolicyConfig
from ase.scenario.parser import parse_file
from ase.storage.trace_store import TraceStore

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
    """Run scenarios through ASE and persist the resulting traces."""
    del config, output, out_file, workers
    scenario_paths = scenario or []
    if not scenario_paths:
        raise typer.Exit(code=1)
    discovered = _collect_scenario_paths(scenario_paths)
    filtered = _filter_by_tags(discovered, tags or [])
    _console.print(
        render_suite_header(
            roots=[path for path in scenario_paths],
            selected_count=len(filtered),
            total_count=len(discovered),
            tags=tags or [],
        )
    )
    if tags and not filtered:
        _console.print(f"[yellow]warning:[/yellow] no scenarios matched tags: {', '.join(tags)}")
        return
    store = TraceStore()
    _run_all(filtered, store, fail_fast=fail_fast, debug=debug)


def _run_all(
    paths: list[Path],
    store: TraceStore,
    *,
    fail_fast: bool,
    debug: bool,
) -> None:
    """Execute all requested scenarios and stop early only when requested."""
    import asyncio

    asyncio.run(store.setup())
    failures = 0
    for path in paths:
        try:
            _run_one(path, store, debug=debug)
        except ASEError as exc:
            failures += 1
            _console.print(f"[red]{exc}[/red]")
            if fail_fast:
                break
    asyncio.run(store.close())
    if failures:
        raise typer.Exit(code=1)


def _run_one(path: Path, store: TraceStore, *, debug: bool) -> None:
    """Execute one scenario end to end and persist its trace."""
    scenario = parse_file(path)
    import asyncio

    trace = asyncio.run(SimulationEngine().run(scenario, debug=debug)).trace
    evaluators = _compiled_assertions(scenario.assertions, scenario.policies)
    summary = EvaluationEngine().evaluate(trace, evaluators, {})
    attach_summary(trace, summary)
    asyncio.run(store.save_trace(trace, ase_score=summary.ase_score))
    _render_summary(trace, summary)
    if not summary.passed or trace.status.value not in {"passed"}:
        raise CLIError(f"scenario failed: {scenario.scenario_id}")


def _collect_scenario_paths(paths: list[Path]) -> list[Path]:
    """Expand file and directory inputs into deterministic scenario file paths."""
    explicit: list[Path] = []
    from_dirs: list[Path] = []
    for path in paths:
        if path.is_dir():
            from_dirs.extend(sorted(path.rglob("*.yaml")))
            from_dirs.extend(sorted(path.rglob("*.yml")))
        else:
            explicit.append(path)
    # Silently skip un-parseable files found via directory scanning only.
    valid_from_dirs: list[Path] = []
    seen: set[Path] = set()
    for path in from_dirs:
        try:
            parse_file(path)
        except Exception:
            continue
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            valid_from_dirs.append(path)
    # Explicit paths are always passed through so errors surface to the user.
    for path in explicit:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
    return explicit + valid_from_dirs


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
def _render_summary(trace: object, summary: object) -> None:
    """Print a compact operator-facing outcome for the recovered test path."""
    trace_id = getattr(trace, "trace_id", "unknown")
    scenario_id = getattr(trace, "scenario_id", "unknown")
    passed = getattr(summary, "passed", False)
    score = getattr(summary, "ase_score", 0.0)
    status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
    _console.print(f"{status} {scenario_id} trace={trace_id} ase_score={score:.2f}")


def _compiled_assertions(
    assertions: list[AssertionConfig],
    policies: list[PolicyConfig],
) -> list[AssertionConfig]:
    """Compile policy configs into assertion configs for the shared engine."""
    compiled = list(assertions)
    for policy in policies:
        compiled.append(
            AssertionConfig(
                evaluator=policy.evaluator,
                params=dict(policy.params),
                pillar=policy.pillar,
            )
        )
    return compiled

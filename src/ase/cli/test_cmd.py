"""ase test — run scenarios through ASE's execution and evaluation flow."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ase.artifacts.bundle import (
    SuiteArtifact,
    build_suite_artifact,
    scenario_artifact_from_run,
    trace_relative_path,
)
from ase.artifacts.bundle import (
    render_json as render_suite_json,
)
from ase.artifacts.bundle import (
    render_junit as render_suite_junit,
)
from ase.artifacts.bundle import (
    render_markdown as render_suite_markdown,
)
from ase.artifacts.bundle import (
    render_terminal as render_suite_terminal,
)
from ase.artifacts.bundle import (
    write_bundle as write_suite_bundle,
)
from ase.config.model import OutputFormat
from ase.core.engine import SimulationEngine
from ase.errors import ASEError, CLIError
from ase.evaluation.base import EvaluationSummary
from ase.evaluation.engine import EvaluationEngine
from ase.evaluation.trace_summary import attach_summary
from ase.reporting.terminal import render_suite_header
from ase.scenario.model import AssertionConfig, PolicyConfig
from ase.scenario.parser import parse_file
from ase.storage.trace_store import TraceStore
from ase.trace.builder import TraceBuilder
from ase.trace.model import Trace

_console = Console()


@dataclass(slots=True)
class ScenarioRun:
    """Hold one executed scenario and its computed evaluation state."""

    scenario_path: Path
    trace: Trace
    summary: EvaluationSummary
    failure_reason: str | None
    baseline_trace_id: str | None = None
    baseline_regression: bool = False
    regression_summary: str | None = None

    @property
    def overall_passed(self) -> bool:
        """Return whether the run passed execution, checks, and baseline gate."""
        return (
            self.summary.passed
            and self.trace.status.value == "passed"
            and not self.baseline_regression
        )


def run(
    scenario: Annotated[list[Path] | None, typer.Argument()] = None,
    config: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    output: Annotated[OutputFormat | None, typer.Option("--output", "-o")] = None,
    out_file: Annotated[Path | None, typer.Option("--out-file", "-f")] = None,
    fail_fast: Annotated[bool, typer.Option("--fail-fast")] = False,
    tags: Annotated[list[str] | None, typer.Option("--tag")] = None,
    workers: Annotated[int, typer.Option("--workers", "-w")] = 4,
    debug: Annotated[bool, typer.Option("--debug")] = False,
    artifacts_dir: Annotated[
        Path | None,
        typer.Option("--artifacts-dir", help="Write a self-contained suite artifact bundle."),
    ] = None,
    compare_to_baseline: Annotated[
        bool,
        typer.Option(
            "--compare-to-baseline",
            help="Compare each scenario to its pinned baseline and fail on regressions.",
        ),
    ] = False,
) -> None:
    """Run scenarios through ASE and persist the resulting traces."""
    del config, workers
    scenario_paths = scenario or []
    if not scenario_paths:
        raise typer.Exit(code=1)
    discovered = _collect_scenario_paths(scenario_paths)
    filtered = _filter_by_tags(discovered, tags or [])
    if not _is_bundle_target(out_file):
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
    runs = _run_all(
        filtered,
        store,
        fail_fast=fail_fast,
        debug=debug,
        show_runs=output is None,
        compare_to_baseline=compare_to_baseline,
    )
    suite = _build_suite_artifact(filtered, runs, output)
    _write_suite_output(
        suite,
        runs,
        output=output,
        out_file=out_file,
        artifacts_dir=artifacts_dir,
        show_terminal_summary=output is None,
    )
    if any(not run.overall_passed for run in runs):
        raise typer.Exit(code=1)


def _run_all(
    paths: list[Path],
    store: TraceStore,
    *,
    fail_fast: bool,
    debug: bool,
    show_runs: bool,
    compare_to_baseline: bool,
) -> list[ScenarioRun]:
    """Execute all requested scenarios and stop early only when requested."""
    asyncio.run(store.setup())
    runs: list[ScenarioRun] = []
    for path in paths:
        try:
            run = _run_one(
                path,
                store,
                debug=debug,
                show_runs=show_runs,
                compare_to_baseline=compare_to_baseline,
            )
        except ASEError as exc:
            run = _failed_run(path, str(exc))
            asyncio.run(store.save_trace(run.trace, ase_score=run.summary.ase_score))
            if show_runs:
                _render_summary(run)
            runs.append(run)
            if fail_fast:
                break
            continue
        runs.append(run)
        if fail_fast and not run.overall_passed:
            break
    asyncio.run(store.close())
    return runs


def _run_one(
    path: Path,
    store: TraceStore,
    *,
    debug: bool,
    show_runs: bool,
    compare_to_baseline: bool,
) -> ScenarioRun:
    """Execute one scenario end to end and persist its trace."""
    scenario = parse_file(path)
    trace = asyncio.run(SimulationEngine().run(scenario, debug=debug)).trace
    evaluators = _compiled_assertions(scenario.assertions, scenario.policies)
    summary = EvaluationEngine().evaluate(trace, evaluators, {})
    attach_summary(trace, summary)
    asyncio.run(store.save_trace(trace, ase_score=summary.ase_score))
    baseline_trace_id, baseline_regression, regression_summary = _compare_to_baseline(
        scenario_id=scenario.scenario_id,
        trace=trace,
        store=store,
        enabled=compare_to_baseline or scenario.baselines is not None,
    )
    run = ScenarioRun(
        scenario_path=path,
        trace=trace,
        summary=summary,
        failure_reason=_failure_reason(
            trace,
            summary,
            baseline_regression=baseline_regression,
            regression_summary=regression_summary,
        ),
        baseline_trace_id=baseline_trace_id,
        baseline_regression=baseline_regression,
        regression_summary=regression_summary,
    )
    if show_runs:
        _render_summary(run)
    return run


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


def _render_summary(run: ScenarioRun) -> None:
    """Print a user-facing outcome block with the next best follow-up command."""
    status = "[green]PASS[/green]" if run.overall_passed else "[red]FAIL[/red]"
    _console.print(f"{status} {run.trace.scenario_id}")
    _console.print(f"  Run ID: {run.trace.trace_id}")
    _console.print(f"  ASE score: {run.summary.ase_score:.2f}")
    _console.print(f"  Run result: {'passed' if run.overall_passed else 'failed'}")
    _console.print(f"  Checks: {_checks_status(run.summary)}")
    if run.failure_reason is not None:
        headline, details = _summarize_reason(run.failure_reason)
        _console.print(f"  [yellow]Why it failed:[/yellow] {headline}")
        if details is not None:
            _console.print(f"  Details: {details}")
    elif run.overall_passed:
        _console.print("  Why it passed: The agent run completed and checks passed.")
    _console.print("  What happened:")
    for item in _what_happened(run):
        _console.print(f"  - {item}")
    _console.print(f"  Next: ase history --trace-id {run.trace.trace_id}")


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


def _failure_reason(
    trace: Trace,
    summary: EvaluationSummary,
    *,
    baseline_regression: bool = False,
    regression_summary: str | None = None,
) -> str | None:
    """Return the highest-signal reason why a run did not fully pass."""
    if baseline_regression and regression_summary:
        return regression_summary
    if trace.status.value != "passed":
        if trace.error_message:
            return trace.error_message.strip()
        return f"The agent run ended with status '{trace.status.value}'."
    if summary.passed:
        return None
    if summary.failing_evaluators:
        return "Checks failed: " + ", ".join(summary.failing_evaluators)
    return "Checks failed."


def _checks_status(summary: EvaluationSummary) -> str:
    """Render a compact user-facing checks summary."""
    state = "passed" if summary.passed else "failed"
    return f"{state} ({summary.passed_count}/{summary.total})"


def _summarize_reason(reason: str) -> tuple[str, str | None]:
    """Split long failure reasons into a headline and optional detail."""
    normalized = " ".join(reason.split())
    if len(normalized) <= 140:
        return normalized, None
    parts = normalized.split(". ", 1)
    headline = parts[0].strip()
    if not headline.endswith("."):
        headline += "."
    details: str | None = parts[1].strip() if len(parts) > 1 else normalized
    if details == headline:
        details = None
    return headline, details


def _what_happened(run: ScenarioRun) -> list[str]:
    """Explain the run outcome in plain language."""
    items = []
    if run.trace.status.value == "passed":
        items.append("The agent run completed successfully.")
    else:
        items.append(f"The agent run ended with status '{run.trace.status.value}'.")
    if run.summary.passed:
        items.append("Checks passed.")
    else:
        items.append("Checks failed.")
    if run.baseline_regression:
        items.append("This run regressed against the pinned baseline.")
    elif run.baseline_trace_id is not None:
        items.append("No regression was detected against the pinned baseline.")
    return items


def _failed_run(path: Path, reason: str) -> ScenarioRun:
    """Create a synthetic failed run so suite output can stay complete."""
    try:
        scenario = parse_file(path)
        scenario_id = scenario.scenario_id
        scenario_name = scenario.name
    except Exception:
        scenario_id = path.stem
        scenario_name = path.name
    from ase.trace.model import TraceStatus

    trace = TraceBuilder(scenario_id, scenario_name).finish(
        status=TraceStatus.ERROR,
        error_message=reason,
    )
    summary = EvaluationSummary(
        trace_id=trace.trace_id,
        scenario_id=scenario_id,
        passed=False,
        ase_score=0.0,
        total=0,
        passed_count=0,
        failed_count=0,
        results=[],
        pillar_scores={},
        failing_evaluators=[],
    )
    return ScenarioRun(
        scenario_path=path,
        trace=trace,
        summary=summary,
        failure_reason=reason,
    )


def _compare_to_baseline(
    *,
    scenario_id: str | None = None,
    scenario: object | None = None,
    trace: Trace,
    summary: EvaluationSummary | None = None,
    store: TraceStore,
    enabled: bool = True,
) -> tuple[str | None, bool, str | None]:
    """Compare the current run to a pinned baseline when requested."""
    del summary
    resolved_scenario_id = scenario_id
    if resolved_scenario_id is None and scenario is not None:
        resolved_scenario_id = getattr(scenario, "scenario_id", None)
    if resolved_scenario_id is None:
        raise CLIError("baseline comparison requires a scenario_id")
    if not enabled:
        return None, False, None
    baseline = asyncio.run(store.get_baseline(resolved_scenario_id))
    if baseline is None:
        return None, False, None
    baseline_trace_id = baseline["trace_id"]
    baseline_trace = asyncio.run(store.get_trace(baseline_trace_id))
    if baseline_trace is None:
        return (
            baseline_trace_id,
            True,
            f"Regression vs baseline {baseline_trace_id}: baseline trace is missing",
        )
    regressions: list[str] = []
    if baseline_trace.status.value == "passed" and trace.status.value != "passed":
        regressions.append(f"run result passed -> {trace.status.value}")
    baseline_checks = bool(baseline_trace.evaluation and baseline_trace.evaluation.passed)
    candidate_checks = bool(trace.evaluation and trace.evaluation.passed)
    if baseline_checks and not candidate_checks:
        regressions.append("checks passed -> failed")
    if not regressions:
        return baseline_trace_id, False, None
    return (
        baseline_trace_id,
        True,
        f"Regression vs baseline {baseline_trace_id}: " + "; ".join(regressions),
    )


def _build_suite_artifact(
    roots: list[Path],
    runs: list[ScenarioRun],
    output: OutputFormat | None,
) -> SuiteArtifact:
    """Build one suite artifact from completed scenario runs."""
    scenarios = [
        scenario_artifact_from_run(
            scenario_path=run.scenario_path,
            trace=run.trace,
            trace_path=trace_relative_path(run.trace.scenario_id),
            execution_status=run.trace.status.value,
            run_result="passed" if run.overall_passed else "failed",
            ase_checks=_checks_status(run.summary),
            ase_score=run.summary.ase_score,
            run_type=(
                run.trace.runtime_provenance.mode
                if run.trace.runtime_provenance
                else "unknown"
            ),
            framework=(
                run.trace.runtime_provenance.framework
                if run.trace.runtime_provenance
                else None
            ),
            tool_calls=run.trace.metrics.total_tool_calls,
            llm_calls=run.trace.metrics.total_llm_calls,
            main_reason=run.failure_reason,
            baseline_trace_id=run.baseline_trace_id,
            baseline_regression=run.baseline_regression,
            regression_summary=run.regression_summary,
        )
        for run in runs
    ]
    return build_suite_artifact(
        suite_id=f"ase-suite-{int(time.time())}",
        roots=roots,
        output_format=output,
        scenarios=scenarios,
        regressions=sum(1 for run in runs if run.baseline_regression),
    )


def _write_suite_output(
    suite: SuiteArtifact,
    runs: list[ScenarioRun],
    *,
    output: OutputFormat | None,
    out_file: Path | None,
    artifacts_dir: Path | None,
    show_terminal_summary: bool,
) -> None:
    """Render suite-level output and optional artifact bundles."""
    traces = {run.trace.trace_id: run.trace for run in runs}
    if artifacts_dir is not None:
        write_suite_bundle(artifacts_dir, suite, traces)
        _console.print(f"[dim]Artifacts: {artifacts_dir}[/dim]")
    if _is_bundle_target(out_file):
        assert out_file is not None
        write_suite_bundle(out_file, suite, traces)
        return
    selected_output = output or OutputFormat.TERMINAL
    rendered = _render_suite_output(suite, traces, selected_output)
    if out_file is not None:
        suffix = "\n" if not rendered.endswith("\n") else ""
        out_file.write_text(rendered + suffix, encoding="utf-8")
    elif output is not None or show_terminal_summary:
        _console.print(rendered)


def _render_suite_output(
    suite: SuiteArtifact,
    traces: dict[str, Trace],
    output: OutputFormat,
) -> str:
    """Render suite output in the requested format."""
    if output == OutputFormat.JSON:
        return render_suite_json(suite)
    if output == OutputFormat.MARKDOWN:
        return render_suite_markdown(suite)
    if output == OutputFormat.JUNIT:
        return render_suite_junit(suite, traces)
    if output == OutputFormat.TERMINAL:
        return render_suite_terminal(suite)
    raise CLIError(f"unsupported test output format: {output}")


def _is_bundle_target(path: Path | None) -> bool:
    """Return whether the output path should be treated as a suite artifact bundle."""
    if path is None:
        return False
    return path.exists() and path.is_dir() or path.suffix == ""

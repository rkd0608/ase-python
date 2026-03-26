"""ase compare — diff two saved ASE traces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from ase.config.model import OutputFormat
from ase.errors import CLIError, TraceSerializationError
from ase.trace.model import Trace

_console = Console()


def run(
    baseline: Annotated[Path, typer.Argument(help="Baseline native ASE trace JSON file.")],
    candidate: Annotated[Path, typer.Argument(help="Candidate native ASE trace JSON file.")],
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format."),
    ] = OutputFormat.TERMINAL,
) -> None:
    """Compare two traces by stable runtime, evaluation, and metric fields."""
    try:
        baseline_trace = _load_trace(baseline)
        candidate_trace = _load_trace(candidate)
        diff = _build_diff(baseline_trace, candidate_trace)
        if output == OutputFormat.JSON:
            _console.print(json.dumps(diff, indent=2))
            return
        if output == OutputFormat.MARKDOWN:
            _console.print(_to_markdown(diff))
            return
        if output != OutputFormat.TERMINAL:
            raise CLIError(f"unsupported compare output format: {output}")
        _console.print(_to_terminal_text(diff))
    except (CLIError, TraceSerializationError) as exc:
        _console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


def _load_trace(path: Path) -> Trace:
    """Load one native ASE trace with contextual parse errors."""
    try:
        return Trace.model_validate_json(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TraceSerializationError(f"failed to read trace file {path}: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise TraceSerializationError(f"failed to parse trace file {path}: {exc}") from exc


def _build_diff(baseline: Trace, candidate: Trace) -> dict[str, Any]:
    """Produce a small, stable diff for operator comparison workflows."""
    base_eval = baseline.evaluation
    cand_eval = candidate.evaluation
    base_runtime = baseline.runtime_provenance
    cand_runtime = candidate.runtime_provenance
    added = sorted(
        set(cand_eval.failing_evaluators if cand_eval else [])
        - set(base_eval.failing_evaluators if base_eval else [])
    )
    removed = sorted(
        set(base_eval.failing_evaluators if base_eval else [])
        - set(cand_eval.failing_evaluators if cand_eval else [])
    )
    baseline_trajectory = _trajectory_sequence(baseline)
    candidate_trajectory = _trajectory_sequence(candidate)
    baseline_match = _trajectory_match_percent(baseline_trajectory, candidate_trajectory)
    candidate_match = _trajectory_match_percent(candidate_trajectory, baseline_trajectory)
    trajectory_changed = baseline_trajectory != candidate_trajectory
    return {
        "baseline_trace_id": baseline.trace_id,
        "candidate_trace_id": candidate.trace_id,
        "scenario_ids": [baseline.scenario_id, candidate.scenario_id],
        "runtime_mode": [
            base_runtime.mode if base_runtime else None,
            cand_runtime.mode if cand_runtime else None,
        ],
        "framework": [
            base_runtime.framework if base_runtime else None,
            cand_runtime.framework if cand_runtime else None,
        ],
        "status": [baseline.status, candidate.status],
        "evaluation_passed": [
            base_eval.passed if base_eval else None,
            cand_eval.passed if cand_eval else None,
        ],
        "ase_score_delta": (cand_eval.ase_score if cand_eval else 0.0)
        - (base_eval.ase_score if base_eval else 0.0),
        "failing_evaluators_added": added,
        "failing_evaluators_removed": removed,
        "metrics": {
            "tool_calls": [
                baseline.metrics.total_tool_calls,
                candidate.metrics.total_tool_calls,
            ],
            "llm_calls": [
                baseline.metrics.total_llm_calls,
                candidate.metrics.total_llm_calls,
            ],
            "tokens": [
                baseline.metrics.total_tokens_used,
                candidate.metrics.total_tokens_used,
            ],
            "duration_ms": [
                baseline.metrics.total_duration_ms,
                candidate.metrics.total_duration_ms,
            ],
            "tool_breakdown": [
                baseline.metrics.tool_call_breakdown,
                candidate.metrics.tool_call_breakdown,
            ],
        },
        "same_scenario": baseline.scenario_id == candidate.scenario_id,
        "trajectory": {
            "baseline": baseline_trajectory,
            "candidate": candidate_trajectory,
            "baseline_match_percent": baseline_match,
            "candidate_match_percent": candidate_match,
            "changed": trajectory_changed,
        },
    }


def _to_terminal_text(diff: dict[str, Any]) -> str:
    """Render a compact diff for direct terminal use."""
    metrics = diff["metrics"]
    lines = [
        "◆ ASE Compare",
        f"baseline: {diff['baseline_trace_id']}",
        f"candidate: {diff['candidate_trace_id']}",
        f"scenario_ids: {diff['scenario_ids'][0]} -> {diff['scenario_ids'][1]}",
        f"runtime_mode: {diff['runtime_mode'][0]} -> {diff['runtime_mode'][1]}",
        f"framework: {diff['framework'][0]} -> {diff['framework'][1]}",
        f"status: {diff['status'][0]} -> {diff['status'][1]}",
        f"evaluation: {diff['evaluation_passed'][0]} -> {diff['evaluation_passed'][1]}",
        f"ase_score_delta: {diff['ase_score_delta']:.2f}",
        "Efficiency Comparison",
        f"  Steps (avg): {metrics['tool_calls'][0]} -> {metrics['tool_calls'][1]}",
        f"  Tokens (avg): {metrics['tokens'][0]} -> {metrics['tokens'][1]}",
    ]
    if diff["same_scenario"]:
        trajectory = diff["trajectory"]
        lines.append(
            "  Trajectory Match: "
            f"{trajectory['baseline_match_percent']:.1f}% -> "
            f"{trajectory['candidate_match_percent']:.1f}%"
        )
        if trajectory["changed"]:
            lines.extend(
                [
                    "Trajectory Diffs (1 scenario changed)",
                    f"  {diff['scenario_ids'][0]}:",
                    f"    baseline: {trajectory['baseline']}",
                    f"    candidate: {trajectory['candidate']}",
                ]
            )
    else:
        lines.append("Trajectory Diffs: skipped (scenarios differ between baseline and candidate)")
    return "\n".join(lines)


def _to_markdown(diff: dict[str, Any]) -> str:
    """Render a short Markdown diff for CI and review surfaces."""
    metrics = diff["metrics"]
    lines = [
        "# ASE Trace Diff",
        "",
        f"- Baseline: `{diff['baseline_trace_id']}`",
        f"- Candidate: `{diff['candidate_trace_id']}`",
        f"- Status: `{diff['status'][0]}` -> `{diff['status'][1]}`",
        f"- Evaluation: `{diff['evaluation_passed'][0]}` -> `{diff['evaluation_passed'][1]}`",
        f"- ASE score delta: `{diff['ase_score_delta']:.2f}`",
        f"- Tool calls: `{metrics['tool_calls'][0]}` -> `{metrics['tool_calls'][1]}`",
    ]
    if diff["same_scenario"]:
        lines.append(
            "- Trajectory match: "
            f"`{diff['trajectory']['baseline_match_percent']:.1f}%` -> "
            f"`{diff['trajectory']['candidate_match_percent']:.1f}%`"
        )
    return "\n".join(lines)


def _trajectory_sequence(trace: Trace) -> list[str]:
    sequence: list[str] = []
    for event in trace.events:
        if event.tool_call is None:
            continue
        payload = event.tool_call.payload or {}
        tool_name = payload.get("tool_name")
        if isinstance(tool_name, str) and tool_name:
            sequence.append(tool_name)
        else:
            sequence.append(event.tool_call.target)
    return sequence


def _trajectory_match_percent(left: list[str], right: list[str]) -> float:
    if not left:
        return 100.0
    matches = sum(1 for idx, value in enumerate(left) if idx < len(right) and right[idx] == value)
    return (matches / len(left)) * 100.0

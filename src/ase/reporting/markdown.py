"""Markdown report helpers for ASE summaries, traces, and suite artifacts."""

from __future__ import annotations

from ase.evaluation.base import EvaluationSummary
from ase.trace.model import Trace


def to_string(summary: EvaluationSummary | None = None, trace: Trace | None = None) -> str:
    """Render a compact Markdown report."""
    if trace is not None:
        return "\n".join(
            [
                "# ASE Trace Report",
                "",
                f"- Trace ID: `{trace.trace_id}`",
                f"- Scenario: `{trace.scenario_id}`",
                f"- Status: `{trace.status.value}`",
                f"- Checks: `{_checks_status(trace)}`",
                f"- Tool calls: `{trace.metrics.total_tool_calls}`",
            ]
        )
    assert summary is not None
    return "\n".join(
        [
            "# ASE Evaluation Summary",
            "",
            f"- Scenario: `{summary.scenario_id}`",
            f"- Passed: `{summary.passed}`",
            f"- ASE score: `{summary.ase_score:.2f}`",
            f"- Assertions: `{summary.passed_count}` passed / `{summary.failed_count}` failed",
        ]
    )


def suite_to_string(suite: object) -> str:
    """Render one suite artifact as Markdown."""
    suite_id = getattr(suite, "suite_id", "unknown")
    run_result = getattr(suite, "run_result", "unknown")
    checks_result = getattr(suite, "checks_result", "unknown")
    total = getattr(suite, "total_scenarios", 0)
    passed = getattr(suite, "passed_scenarios", 0)
    failed = getattr(suite, "failed_scenarios", 0)
    regressions = getattr(suite, "regression_count", 0)
    lines = [
        "# ASE Test Suite Artifact",
        "",
        f"- Suite ID: `{suite_id}`",
        f"- Run result: `{run_result}`",
        f"- Checks: `{checks_result}`",
        f"- Scenarios: `{total}`",
        f"- Passed: `{passed}`",
        f"- Failed: `{failed}`",
    ]
    if regressions:
        lines.append(f"- Regressions: `{regressions}`")
    lines.extend(["", "## Scenarios"])
    for scenario in getattr(suite, "scenarios", []):
        lines.append(
            f"- `{scenario.scenario_id}`: `{scenario.run_result}` "
            f"(execution `{scenario.execution_status}`, checks `{scenario.ase_checks}`, "
            f"score `{scenario.ase_score:.2f}`)"
        )
        if scenario.main_reason:
            lines.append(f"  - Main reason: `{scenario.main_reason}`")
        if scenario.regression_summary:
            lines.append(f"  - Regression: `{scenario.regression_summary}`")
    return "\n".join(lines)


def _checks_status(trace: Trace) -> str:
    """Return a compact checks label for trace reports."""
    if trace.evaluation is None:
        return "not included in this trace"
    return "passed" if trace.evaluation.passed else "failed"

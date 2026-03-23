"""Markdown report helpers for ASE summaries and traces."""

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

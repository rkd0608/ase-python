"""Rich terminal renderers for ASE summaries."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ase.evaluation.base import EvaluationSummary, Pillar
from ase.trace.model import Trace


def render(
    summary: EvaluationSummary,
    console: Console | None = None,
    trace: Trace | None = None,
) -> None:
    """Render a full terminal report with optional trace context."""
    target = console or Console()
    target.print(_summary_panel(summary))
    target.print(_results_table(summary))
    if trace is not None and trace.stderr_output:
        target.print(Panel(trace.stderr_output, title="Agent stderr"))


def render_compact(summary: EvaluationSummary, console: Console | None = None) -> None:
    """Render a compact one-panel summary for short workflows."""
    target = console or Console()
    target.print(_summary_panel(summary))


def _summary_panel(summary: EvaluationSummary) -> Panel:
    """Build the high-level summary panel."""
    status = "PASS" if summary.passed else "FAIL"
    body = "\n".join(
        [
            f"Scenario: {summary.scenario_id}",
            f"Trace ID: {summary.trace_id}",
            f"ASE Score: {summary.ase_score:.4f}",
            "Assertions: "
            f"{summary.passed_count} passed / "
            f"{summary.failed_count} failed / "
            f"{summary.total} total",
        ]
    )
    return Panel(body, title=f"ASE Result — {status}")


def _results_table(summary: EvaluationSummary) -> Table:
    """Build the evaluator result table."""
    table = Table(title="Assertions")
    table.add_column("Evaluator")
    table.add_column("Pillar")
    table.add_column("Score")
    table.add_column("Message")
    for result in summary.results:
        table.add_row(
            result.evaluator,
            result.pillar.value,
            f"{result.score:.2f}",
            result.message,
        )
    return table


__all__ = ["EvaluationSummary", "Pillar", "Trace", "render", "render_compact"]

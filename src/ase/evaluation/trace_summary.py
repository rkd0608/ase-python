"""Helpers for attaching evaluation summaries to traces."""

from __future__ import annotations

from ase.evaluation.base import EvaluationSummary
from ase.trace.model import Trace, TraceEvaluation


def attach_summary(trace: Trace, summary: EvaluationSummary) -> None:
    """Persist a computed evaluation summary onto a trace."""
    trace.evaluation = TraceEvaluation(
        passed=summary.passed,
        ase_score=summary.ase_score,
        total=summary.total,
        passed_count=summary.passed_count,
        failed_count=summary.failed_count,
        failing_evaluators=list(summary.failing_evaluators),
    )


def summary_from_trace(trace: Trace) -> EvaluationSummary | None:
    """Rebuild a lightweight summary view from persisted trace evaluation data."""
    if trace.evaluation is None:
        return None
    evaluation = trace.evaluation
    return EvaluationSummary(
        trace_id=trace.trace_id,
        scenario_id=trace.scenario_id,
        passed=evaluation.passed,
        ase_score=evaluation.ase_score,
        total=evaluation.total,
        passed_count=evaluation.passed_count,
        failed_count=evaluation.failed_count,
        pillar_scores={},
        failing_evaluators=list(evaluation.failing_evaluators),
    )

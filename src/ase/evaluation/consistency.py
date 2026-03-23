"""Consistency evaluators used for baseline-style comparisons."""

from __future__ import annotations

from typing import Any

from ase.evaluation.base import AssertionResult, Evaluator, Pillar


class SameToolCallsEvaluator(Evaluator):
    """Compare tool-call counts against a provided baseline trace."""

    @property
    def name(self) -> str:
        return "same_tool_calls"

    @property
    def pillar(self) -> Pillar:
        return Pillar.CONSISTENCY

    def evaluate(self, trace: object, params: dict[str, Any], **context: Any) -> AssertionResult:
        baseline = context.get("baseline_trace")
        if baseline is None:
            return _passing(self.name, self.pillar, "no baseline provided")
        current = getattr(getattr(trace, "metrics", None), "total_tool_calls", 0)
        previous = getattr(getattr(baseline, "metrics", None), "total_tool_calls", 0)
        passed = current == previous
        return AssertionResult(
            evaluator=self.name,
            pillar=self.pillar,
            passed=passed,
            score=1.0 if passed else 0.0,
            message=f"tool calls {current} vs baseline {previous}",
            details={"current": current, "baseline": previous},
        )


class SameMetricsEvaluator(Evaluator):
    """Compare stable metrics against a provided baseline trace."""

    @property
    def name(self) -> str:
        return "same_metrics"

    @property
    def pillar(self) -> Pillar:
        return Pillar.CONSISTENCY

    def evaluate(self, trace: object, params: dict[str, Any], **context: Any) -> AssertionResult:
        baseline = context.get("baseline_trace")
        if baseline is None:
            return _passing(self.name, self.pillar, "no baseline provided")
        current_metrics = getattr(trace, "metrics", None)
        baseline_metrics = getattr(baseline, "metrics", None)
        keys = ["total_tool_calls", "total_llm_calls", "total_tokens_used"]
        deltas = {
            key: getattr(current_metrics, key, 0) - getattr(baseline_metrics, key, 0)
            for key in keys
        }
        passed = all(delta == 0 for delta in deltas.values())
        return AssertionResult(
            evaluator=self.name,
            pillar=self.pillar,
            passed=passed,
            score=1.0 if passed else 0.0,
            message="metrics match baseline" if passed else "metrics differ from baseline",
            details=deltas,
        )


def _passing(evaluator: str, pillar: Pillar, message: str) -> AssertionResult:
    """Return a neutral passing result when no baseline context exists."""
    return AssertionResult(
        evaluator=evaluator,
        pillar=pillar,
        passed=True,
        score=1.0,
        message=message,
    )

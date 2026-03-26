"""Efficiency evaluators for cost and tool-usage limits.

These evaluators keep ASE's efficiency scoring generic by operating on trace
metrics only. They do not assume any framework-specific runtime semantics.
"""

from __future__ import annotations

from typing import Any

from ase.evaluation.base import AssertionResult, Evaluator, Pillar
from ase.trace.model import Trace

DEFAULT_USD_PER_1K_TOKENS = 0.01


class MaxToolCallsEvaluator(Evaluator):
    """Cap observable tool usage so regressions show up as wasted actions."""

    @property
    def name(self) -> str:
        return "max_tool_calls"

    @property
    def pillar(self) -> Pillar:
        return Pillar.EFFICIENCY

    def evaluate(self, trace: object, params: dict[str, Any], **context: Any) -> AssertionResult:
        del context
        resolved = _trace(trace)
        maximum = _required_int(params, "maximum")
        actual = resolved.metrics.total_tool_calls
        passed = actual <= maximum
        return AssertionResult(
            evaluator=self.name,
            pillar=self.pillar,
            passed=passed,
            score=1.0 if passed else 0.0,
            message=_limit_message("tool call(s)", actual, maximum, passed),
            details={"maximum": maximum, "actual": actual},
        )


class MaxTokensEvaluator(Evaluator):
    """Bound token usage using trace-level request and response metrics."""

    @property
    def name(self) -> str:
        return "max_tokens"

    @property
    def pillar(self) -> Pillar:
        return Pillar.EFFICIENCY

    def evaluate(self, trace: object, params: dict[str, Any], **context: Any) -> AssertionResult:
        del context
        resolved = _trace(trace)
        maximum = _required_int(params, "maximum")
        actual = resolved.metrics.total_tokens_used
        passed = actual <= maximum
        return AssertionResult(
            evaluator=self.name,
            pillar=self.pillar,
            passed=passed,
            score=1.0 if passed else 0.0,
            message=_limit_message("token(s)", actual, maximum, passed),
            details={"maximum": maximum, "actual": actual},
        )


class CostProjectionEvaluator(Evaluator):
    """Project a simple token-based spend ceiling from the trace metrics."""

    @property
    def name(self) -> str:
        return "cost_projection"

    @property
    def pillar(self) -> Pillar:
        return Pillar.EFFICIENCY

    def evaluate(self, trace: object, params: dict[str, Any], **context: Any) -> AssertionResult:
        del context
        resolved = _trace(trace)
        maximum = _required_float(params, "maximum_usd")
        rate = _optional_float(params, "usd_per_1k_tokens", DEFAULT_USD_PER_1K_TOKENS)
        tokens = resolved.metrics.total_tokens_used
        projected = (tokens / 1000.0) * rate
        passed = projected <= maximum
        return AssertionResult(
            evaluator=self.name,
            pillar=self.pillar,
            passed=passed,
            score=1.0 if passed else 0.0,
            message=_cost_message(projected, maximum, passed),
            details={
                "maximum_usd": maximum,
                "projected_usd": projected,
                "usd_per_1k_tokens": rate,
                "tokens": tokens,
            },
        )


class SolveRateEvaluator(Evaluator):
    """Measures efficiency as ratio of ideal tool-call steps to actual steps."""

    @property
    def name(self) -> str:
        return "solve_rate"

    @property
    def pillar(self) -> Pillar:
        return Pillar.EFFICIENCY

    def evaluate(self, trace: object, params: dict[str, Any], **context: Any) -> AssertionResult:
        del context
        resolved = _trace(trace)
        ideal_steps = _required_int(params, "ideal_steps")
        actual_steps = resolved.metrics.total_tool_calls
        score = _ratio_score(ideal_steps, actual_steps)
        return AssertionResult(
            evaluator=self.name,
            pillar=self.pillar,
            passed=score >= 70.0,
            score=score,
            message=f"solve rate ideal/actual = {ideal_steps}/{actual_steps} ({score:.2f})",
            details={"ideal_steps": ideal_steps, "actual_steps": actual_steps},
        )


class LatencyRatioEvaluator(Evaluator):
    """Measures runtime efficiency using target latency vs observed latency."""

    @property
    def name(self) -> str:
        return "latency_ratio"

    @property
    def pillar(self) -> Pillar:
        return Pillar.EFFICIENCY

    def evaluate(self, trace: object, params: dict[str, Any], **context: Any) -> AssertionResult:
        del context
        resolved = _trace(trace)
        target_ms = _required_float(params, "target_ms")
        actual_ms = float(resolved.metrics.total_duration_ms)
        score = _ratio_score(target_ms, actual_ms)
        return AssertionResult(
            evaluator=self.name,
            pillar=self.pillar,
            passed=score >= 70.0,
            score=score,
            message=f"latency ratio target/actual = {target_ms:.2f}/{actual_ms:.2f} ({score:.2f})",
            details={"target_ms": target_ms, "actual_ms": actual_ms},
        )


class CostEfficiencyEvaluator(Evaluator):
    """Scores token consumption efficiency against a configurable token budget."""

    @property
    def name(self) -> str:
        return "cost_efficiency"

    @property
    def pillar(self) -> Pillar:
        return Pillar.EFFICIENCY

    def evaluate(self, trace: object, params: dict[str, Any], **context: Any) -> AssertionResult:
        del context
        resolved = _trace(trace)
        budget_tokens = _required_int(params, "budget_tokens")
        actual_tokens = resolved.metrics.total_tokens_used
        score = _ratio_score(budget_tokens, actual_tokens)
        return AssertionResult(
            evaluator=self.name,
            pillar=self.pillar,
            passed=score >= 70.0,
            score=score,
            message=(
                "token efficiency budget/actual = "
                f"{budget_tokens}/{actual_tokens} ({score:.2f})"
            ),
            details={"budget_tokens": budget_tokens, "actual_tokens": actual_tokens},
        )


def _required_int(params: dict[str, Any], key: str) -> int:
    """Parse integer limits with a stable configuration error."""
    if key not in params:
        raise ValueError(f"missing required param: {key}")
    return int(params[key])


def _required_float(params: dict[str, Any], key: str) -> float:
    """Parse float limits with a stable configuration error."""
    if key not in params:
        raise ValueError(f"missing required param: {key}")
    return float(params[key])


def _optional_float(params: dict[str, Any], key: str, default: float) -> float:
    """Parse optional cost-rate parameters with one neutral fallback."""
    value = params.get(key)
    if value is None:
        return default
    return float(value)


def _limit_message(label: str, actual: int, maximum: int, passed: bool) -> str:
    """Render stable operator-facing messages for ceiling checks."""
    if passed:
        return f"agent made {actual}/{maximum} {label}"
    return f"expected <={maximum} {label}, got {actual}"


def _cost_message(projected: float, maximum: float, passed: bool) -> str:
    """Render stable operator-facing messages for projected cost checks."""
    if passed:
        return f"projected cost ${projected:.4f} <= ${maximum:.4f}"
    return f"expected projected cost <= ${maximum:.4f}, got ${projected:.4f}"


def _trace(value: object) -> Trace:
    """Validate the generic evaluator input before reading trace metrics."""
    if not isinstance(value, Trace):
        raise ValueError("trace must be a Trace instance")
    return value


def _ratio_score(ideal: float, actual: float) -> float:
    """Compute an efficiency percentage capped at 100 with zero-safe semantics."""
    if ideal <= 0:
        return 100.0
    if actual <= 0:
        return 100.0
    return min(100.0, (ideal / actual) * 100.0)

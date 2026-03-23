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

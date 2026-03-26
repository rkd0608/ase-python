from __future__ import annotations

from ase.evaluation.efficiency import (
    CostEfficiencyEvaluator,
    LatencyRatioEvaluator,
    SolveRateEvaluator,
)
from ase.trace.builder import TraceBuilder
from ase.trace.model import LLMRequestEvent, ToolCallEvent, ToolCallKind


def _trace(*, tool_calls: int = 0, tokens: int = 0, duration_ms: float = 0.0):
    builder = TraceBuilder("scenario", "scenario")
    for _ in range(tool_calls):
        builder.add_tool_call(
            ToolCallEvent(kind=ToolCallKind.HTTP_API, method="GET", target="https://example.com")
        )
    if tokens:
        builder.add_llm_request(
            LLMRequestEvent(model="gpt", prompt_hash="x", token_count_estimate=tokens)
        )
    trace = builder.finish()
    trace.metrics.total_duration_ms = duration_ms
    return trace


def test_solve_rate_perfect() -> None:
    result = SolveRateEvaluator().evaluate(_trace(tool_calls=5), {"ideal_steps": 5})
    assert result.score == 100.0


def test_solve_rate_double() -> None:
    result = SolveRateEvaluator().evaluate(_trace(tool_calls=10), {"ideal_steps": 5})
    assert result.score == 50.0


def test_solve_rate_fewer_than_ideal() -> None:
    result = SolveRateEvaluator().evaluate(_trace(tool_calls=4), {"ideal_steps": 5})
    assert result.score == 100.0


def test_latency_ratio_under_target() -> None:
    result = LatencyRatioEvaluator().evaluate(_trace(duration_ms=1000), {"target_ms": 5000})
    assert result.score == 100.0


def test_latency_ratio_over_target() -> None:
    result = LatencyRatioEvaluator().evaluate(_trace(duration_ms=10000), {"target_ms": 5000})
    assert result.score == 50.0


def test_cost_efficiency_under_budget() -> None:
    result = CostEfficiencyEvaluator().evaluate(_trace(tokens=1000), {"budget_tokens": 2000})
    assert result.score == 100.0


def test_cost_efficiency_over_budget() -> None:
    result = CostEfficiencyEvaluator().evaluate(_trace(tokens=4000), {"budget_tokens": 2000})
    assert result.score == 50.0


def test_cost_efficiency_zero_tokens() -> None:
    result = CostEfficiencyEvaluator().evaluate(_trace(tokens=0), {"budget_tokens": 2000})
    assert result.score == 100.0

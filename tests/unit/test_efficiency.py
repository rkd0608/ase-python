from __future__ import annotations

from ase.evaluation.efficiency import (
    CostProjectionEvaluator,
    MaxTokensEvaluator,
    MaxToolCallsEvaluator,
)
from ase.trace.builder import TraceBuilder
from ase.trace.model import LLMRequestEvent, LLMResponseEvent, ToolCallEvent, ToolCallKind


def test_max_tool_calls_passes_at_limit() -> None:
    trace = (
        TraceBuilder("scenario-1", "Scenario 1")
        .add_tool_call(
            ToolCallEvent(kind=ToolCallKind.HTTP_API, method="POST", target="https://api.example.com/refunds")
        )
        .finish()
    )
    result = MaxToolCallsEvaluator().evaluate(trace, {"maximum": 1})
    assert result.passed is True
    assert result.message == "agent made 1/1 tool call(s)"


def test_max_tokens_fails_when_trace_exceeds_limit() -> None:
    trace = (
        TraceBuilder("scenario-2", "Scenario 2")
        .add_llm_request(
            LLMRequestEvent(model="gpt-test", prompt_hash="abc", token_count_estimate=300)
        )
        .add_llm_response(
            LLMResponseEvent(model="gpt-test", output_tokens=250, finish_reason="stop")
        )
        .finish()
    )
    result = MaxTokensEvaluator().evaluate(trace, {"maximum": 400})
    assert result.passed is False
    assert result.details["actual"] == 550


def test_cost_projection_uses_explicit_rate() -> None:
    trace = (
        TraceBuilder("scenario-3", "Scenario 3")
        .add_llm_request(
            LLMRequestEvent(model="gpt-test", prompt_hash="def", token_count_estimate=1000)
        )
        .finish()
    )
    result = CostProjectionEvaluator().evaluate(
        trace,
        {"maximum_usd": 0.01, "usd_per_1k_tokens": 0.02},
    )
    assert result.passed is False
    assert result.details["projected_usd"] == 0.02

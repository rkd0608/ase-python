from __future__ import annotations

from ase.evaluation.base import AssertionOutcome
from ase.evaluation.efficiency import CostProjectionEvaluator, MaxTokensEvaluator, MaxToolCallsEvaluator
from ase.trace.builder import TraceBuilder
from ase.trace.model import LLMRequestEvent, ToolCallEvent, ToolCallKind, TraceStatus


def test_max_tool_calls_pass_and_fail_cases() -> None:
    passing_trace = TraceBuilder("pass", "pass").finish()
    failing_trace = (
        TraceBuilder("fail", "fail")
        .add_tool_call(ToolCallEvent(kind=ToolCallKind.HTTP_API, method="GET", target="https://example.com"))
        .finish()
    )

    assert MaxToolCallsEvaluator().evaluate(passing_trace, {"maximum": 0}).passed is True
    assert MaxToolCallsEvaluator().evaluate(failing_trace, {"maximum": 0}).passed is False


def test_max_tokens_pass_and_fail_cases() -> None:
    passing_trace = (
        TraceBuilder("pass", "pass")
        .add_llm_request(LLMRequestEvent(model="gpt-test", prompt_hash="a", token_count_estimate=10))
        .finish()
    )
    failing_trace = (
        TraceBuilder("fail", "fail")
        .add_llm_request(LLMRequestEvent(model="gpt-test", prompt_hash="b", token_count_estimate=999))
        .finish()
    )
    assert MaxTokensEvaluator().evaluate(passing_trace, {"maximum": 10}).passed is True
    assert MaxTokensEvaluator().evaluate(failing_trace, {"maximum": 10}).passed is False


def test_cost_projection_pass_and_fail_cases() -> None:
    trace = (
        TraceBuilder("cost", "cost")
        .add_llm_request(LLMRequestEvent(model="gpt-test", prompt_hash="c", token_count_estimate=1000))
        .finish()
    )
    assert CostProjectionEvaluator().evaluate(trace, {"maximum_usd": 0.02, "usd_per_1k_tokens": 0.01}).passed is True
    assert CostProjectionEvaluator().evaluate(trace, {"maximum_usd": 0.009, "usd_per_1k_tokens": 0.01}).passed is False


def test_efficiency_evaluators_handle_empty_model_only_and_error_trace() -> None:
    empty_trace = TraceBuilder("empty", "empty").finish()
    model_only_trace = (
        TraceBuilder("model", "model")
        .add_llm_request(LLMRequestEvent(model="gpt-test", prompt_hash="m", token_count_estimate=5))
        .finish()
    )
    error_trace = TraceBuilder("error", "error").finish(status=TraceStatus.ERROR, error_message="boom")

    assert MaxToolCallsEvaluator().evaluate(empty_trace, {"maximum": 0}).passed is True
    assert MaxToolCallsEvaluator().evaluate(model_only_trace, {"maximum": 0}).passed is True
    assert MaxToolCallsEvaluator().evaluate(error_trace, {"maximum": 0}).passed is True

    assert MaxTokensEvaluator().evaluate(empty_trace, {"maximum": 0}).passed is True
    assert MaxTokensEvaluator().evaluate(model_only_trace, {"maximum": 0}).passed is False
    assert MaxTokensEvaluator().evaluate(error_trace, {"maximum": 0}).passed is True

    assert CostProjectionEvaluator().evaluate(empty_trace, {"maximum_usd": 0.0}).passed is True
    assert CostProjectionEvaluator().evaluate(model_only_trace, {"maximum_usd": 0.0}).passed is False
    assert CostProjectionEvaluator().evaluate(error_trace, {"maximum_usd": 0.0}).passed is True


def test_efficiency_evaluators_return_error_outcome_on_invalid_params() -> None:
    trace = TraceBuilder("invalid", "invalid").finish()
    max_tool_calls = MaxToolCallsEvaluator().evaluate(trace, {"maximum": "oops"})
    max_tokens = MaxTokensEvaluator().evaluate(trace, {"maximum": "oops"})
    cost = CostProjectionEvaluator().evaluate(trace, {"maximum_usd": "oops"})

    assert max_tool_calls.outcome == AssertionOutcome.ERROR
    assert max_tokens.outcome == AssertionOutcome.ERROR
    assert cost.outcome == AssertionOutcome.ERROR

from __future__ import annotations

from ase.evaluation.base import AssertionOutcome
from ase.evaluation.correctness import APICalledEvaluator, ToolCalledEvaluator
from ase.trace.builder import TraceBuilder
from ase.trace.model import (
    LLMRequestEvent,
    ToolCallEvent,
    ToolCallKind,
    TraceStatus,
)


def test_tool_called_pass_and_fail_cases() -> None:
    passing_trace = (
        TraceBuilder("scenario-pass", "Pass")
        .add_tool_call(
            ToolCallEvent(kind=ToolCallKind.HTTP_API, method="GET", target="https://example.com/users")
        )
        .finish()
    )
    failing_trace = TraceBuilder("scenario-fail", "Fail").finish()

    passing = ToolCalledEvaluator().evaluate(passing_trace, {"kind": "http_api", "minimum": 1})
    failing = ToolCalledEvaluator().evaluate(failing_trace, {"kind": "http_api", "minimum": 1})

    assert passing.passed is True
    assert failing.passed is False


def test_api_called_pass_and_fail_cases() -> None:
    passing_trace = (
        TraceBuilder("scenario-pass", "Pass")
        .add_tool_call(
            ToolCallEvent(kind=ToolCallKind.HTTP_API, method="POST", target="https://example.com/orders")
        )
        .finish()
    )
    failing_trace = (
        TraceBuilder("scenario-fail", "Fail")
        .add_tool_call(
            ToolCallEvent(kind=ToolCallKind.DATABASE, method="SELECT", target="orders")
        )
        .finish()
    )

    passing = APICalledEvaluator().evaluate(passing_trace, {"minimum": 1})
    failing = APICalledEvaluator().evaluate(failing_trace, {"minimum": 1})

    assert passing.passed is True
    assert failing.passed is False


def test_correctness_evaluators_handle_empty_model_only_and_error_trace() -> None:
    empty_trace = TraceBuilder("empty", "Empty").finish()
    model_only_trace = (
        TraceBuilder("model", "Model-only")
        .add_llm_request(LLMRequestEvent(model="gpt-test", prompt_hash="abc", token_count_estimate=8))
        .finish()
    )
    error_trace = TraceBuilder("error", "Error").finish(status=TraceStatus.ERROR, error_message="boom")

    tool_eval = ToolCalledEvaluator()
    api_eval = APICalledEvaluator()

    assert tool_eval.evaluate(empty_trace, {"minimum": 1}).passed is False
    assert tool_eval.evaluate(model_only_trace, {"minimum": 1}).passed is False
    assert tool_eval.evaluate(error_trace, {"minimum": 0}).passed is True

    assert api_eval.evaluate(empty_trace, {"minimum": 1}).passed is False
    assert api_eval.evaluate(model_only_trace, {"minimum": 1}).passed is False
    assert api_eval.evaluate(error_trace, {"minimum": 0}).passed is True


def test_correctness_evaluators_return_error_outcome_on_invalid_params() -> None:
    trace = TraceBuilder("invalid", "Invalid params").finish()

    tool_result = ToolCalledEvaluator().evaluate(trace, {"minimum": "abc"})
    api_result = APICalledEvaluator().evaluate(trace, {"minimum": "bad"})

    assert tool_result.outcome == AssertionOutcome.ERROR
    assert "invalid params" in tool_result.message
    assert api_result.outcome == AssertionOutcome.ERROR
    assert "invalid params" in api_result.message

from __future__ import annotations

from ase.evaluation.base import AssertionOutcome
from ase.evaluation.safety import NoPIIEvaluator, NoRawSQLEvaluator, NoUnauthorizedAccessEvaluator
from ase.trace.builder import TraceBuilder
from ase.trace.model import LLMRequestEvent, ToolCallEvent, ToolCallKind, TraceStatus


def test_no_unauthorized_access_pass_and_fail_cases() -> None:
    passing_trace = (
        TraceBuilder("safe", "safe")
        .add_tool_call(ToolCallEvent(kind=ToolCallKind.HTTP_API, method="GET", target="https://example.com/public"))
        .finish()
    )
    failing_trace = (
        TraceBuilder("unsafe", "unsafe")
        .add_tool_call(
            ToolCallEvent(kind=ToolCallKind.HTTP_API, method="GET", target="https://example.com/admin/users")
        )
        .finish()
    )
    assert NoUnauthorizedAccessEvaluator().evaluate(passing_trace, {}).passed is True
    assert NoUnauthorizedAccessEvaluator().evaluate(failing_trace, {}).passed is False


def test_no_pii_pass_and_fail_cases() -> None:
    passing_trace = (
        TraceBuilder("safe", "safe")
        .add_tool_call(
            ToolCallEvent(
                kind=ToolCallKind.HTTP_API,
                method="POST",
                target="https://example.com/profiles",
                payload={"note": "harmless"},
            )
        )
        .finish()
    )
    failing_trace = (
        TraceBuilder("unsafe", "unsafe")
        .add_tool_call(
            ToolCallEvent(
                kind=ToolCallKind.HTTP_API,
                method="POST",
                target="https://example.com/profiles",
                payload={"email": "person@example.com"},
            )
        )
        .finish()
    )
    assert NoPIIEvaluator().evaluate(passing_trace, {}).passed is True
    assert NoPIIEvaluator().evaluate(failing_trace, {}).passed is False


def test_no_raw_sql_pass_and_fail_cases() -> None:
    passing_trace = (
        TraceBuilder("safe", "safe")
        .add_tool_call(
            ToolCallEvent(
                kind=ToolCallKind.DATABASE,
                method="query_builder",
                target="users",
                payload={"query": "users_by_id"},
            )
        )
        .finish()
    )
    failing_trace = (
        TraceBuilder("unsafe", "unsafe")
        .add_tool_call(
            ToolCallEvent(
                kind=ToolCallKind.DATABASE,
                method="run",
                target="users",
                payload={"query": "SELECT * FROM users"},
            )
        )
        .finish()
    )
    assert NoRawSQLEvaluator().evaluate(passing_trace, {}).passed is True
    assert NoRawSQLEvaluator().evaluate(failing_trace, {}).passed is False


def test_safety_evaluators_handle_empty_model_only_and_error_trace() -> None:
    empty_trace = TraceBuilder("empty", "empty").finish()
    model_only_trace = (
        TraceBuilder("model", "model")
        .add_llm_request(
            LLMRequestEvent(model="gpt-test", prompt_hash="abc", token_count_estimate=3)
        )
        .finish()
    )
    error_trace = TraceBuilder("error", "error").finish(
        status=TraceStatus.ERROR, error_message="boom"
    )

    assert NoUnauthorizedAccessEvaluator().evaluate(empty_trace, {}).passed is True
    assert NoUnauthorizedAccessEvaluator().evaluate(model_only_trace, {}).passed is True
    assert NoUnauthorizedAccessEvaluator().evaluate(error_trace, {}).passed is True

    assert NoPIIEvaluator().evaluate(empty_trace, {}).passed is True
    assert NoPIIEvaluator().evaluate(model_only_trace, {}).passed is True
    assert NoPIIEvaluator().evaluate(error_trace, {}).passed is True

    assert NoRawSQLEvaluator().evaluate(empty_trace, {}).passed is True
    assert NoRawSQLEvaluator().evaluate(model_only_trace, {}).passed is True
    assert NoRawSQLEvaluator().evaluate(error_trace, {}).passed is True


def test_safety_evaluators_return_error_outcome_on_invalid_params() -> None:
    trace = TraceBuilder("invalid", "invalid").finish()

    no_auth = NoUnauthorizedAccessEvaluator().evaluate(trace, {"blocked_markers": "admin"})
    no_pii = NoPIIEvaluator().evaluate(trace, {"include_targets": "yes"})
    no_sql = NoRawSQLEvaluator().evaluate(trace, {"query_key": 5})

    assert no_auth.outcome == AssertionOutcome.ERROR
    assert no_pii.outcome == AssertionOutcome.ERROR
    assert no_sql.outcome == AssertionOutcome.ERROR

from __future__ import annotations

from ase.evaluation.trajectory import TrajectoryEvaluator
from ase.trace.builder import TraceBuilder
from ase.trace.model import ToolCallEvent, ToolCallKind


def _trace(sequence: list[str]):
    builder = TraceBuilder("scenario", "scenario")
    for name in sequence:
        builder.add_tool_call(
            ToolCallEvent(
                kind=ToolCallKind.HTTP_API,
                method="POST",
                target=f"https://example.com/{name}",
                payload={"tool_name": name},
            )
        )
    return builder.finish()


def test_perfect_trajectory() -> None:
    expected = ["query_database", "call_stripe", "update_database"]
    result = TrajectoryEvaluator().evaluate(_trace(expected), {"expected_sequence": expected})
    assert result.score == 100.0
    assert result.passed is True


def test_extra_calls_penalized() -> None:
    expected = ["query_database", "call_stripe"]
    actual = ["query_database", "call_stripe", "send_email", "log_audit"]
    result = TrajectoryEvaluator().evaluate(_trace(actual), {"expected_sequence": expected})
    assert result.score < 100.0


def test_missing_calls_penalized() -> None:
    expected = ["query_database", "call_stripe", "update_database"]
    actual = ["query_database", "call_stripe"]
    result = TrajectoryEvaluator().evaluate(_trace(actual), {"expected_sequence": expected})
    assert result.score < 100.0


def test_reordered_calls_penalized() -> None:
    expected = ["query_database", "call_stripe", "update_database"]
    actual = ["call_stripe", "query_database", "update_database"]
    result = TrajectoryEvaluator().evaluate(
        _trace(actual),
        {"expected_sequence": expected, "strict_order": True},
    )
    assert result.score < 100.0


def test_completely_wrong() -> None:
    expected = ["query_database", "call_stripe"]
    actual = ["send_email", "write_file"]
    result = TrajectoryEvaluator().evaluate(_trace(actual), {"expected_sequence": expected})
    assert result.score == 0.0


def test_allow_extra_no_penalty() -> None:
    expected = ["query_database", "call_stripe"]
    actual = ["query_database", "call_stripe", "send_email"]
    result = TrajectoryEvaluator().evaluate(
        _trace(actual),
        {"expected_sequence": expected, "allow_extra": True},
    )
    assert result.score == 100.0


def test_empty_expected() -> None:
    result = TrajectoryEvaluator().evaluate(_trace(["query_database"]), {"expected_sequence": []})
    assert result.passed is True
    assert result.score == 100.0


def test_empty_actual() -> None:
    result = TrajectoryEvaluator().evaluate(
        _trace([]),
        {"expected_sequence": ["query_database"]},
    )
    assert result.score == 0.0
    assert "actual=[]" in result.message


def test_message_shows_diff() -> None:
    expected = ["query_database"]
    actual = ["send_email"]
    result = TrajectoryEvaluator().evaluate(_trace(actual), {"expected_sequence": expected})
    assert "expected=['query_database']" in result.message
    assert "actual=['send_email']" in result.message

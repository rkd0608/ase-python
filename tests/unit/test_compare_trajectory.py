from __future__ import annotations

from ase.cli.compare import _build_diff, _to_terminal_text
from ase.trace.builder import TraceBuilder
from ase.trace.model import ToolCallEvent, ToolCallKind


def _trace(trace_id: str, scenario_id: str, tools: list[str]):
    builder = TraceBuilder(scenario_id, scenario_id)
    for tool in tools:
        builder.add_tool_call(
            ToolCallEvent(
                kind=ToolCallKind.HTTP_API,
                method="POST",
                target=f"https://example.com/{tool}",
                payload={"tool_name": tool},
            )
        )
    trace = builder.finish()
    trace.trace_id = trace_id
    return trace


def test_compare_shows_trajectory_diff() -> None:
    baseline = _trace("trace-a", "refund-happy-path", ["query_db", "query_db", "call_stripe"])
    candidate = _trace("trace-b", "refund-happy-path", ["query_db", "call_stripe"])
    diff = _build_diff(baseline, candidate)
    rendered = _to_terminal_text(diff)
    assert "Trajectory Diffs" in rendered
    assert "baseline: ['query_db', 'query_db', 'call_stripe']" in rendered


def test_compare_identical_trajectories() -> None:
    baseline = _trace("trace-a", "order-lookup", ["query_db"])
    candidate = _trace("trace-b", "order-lookup", ["query_db"])
    diff = _build_diff(baseline, candidate)
    rendered = _to_terminal_text(diff)
    assert "Trajectory Diffs (1 scenario changed)" not in rendered


def test_compare_missing_scenario() -> None:
    baseline = _trace("trace-a", "scenario-a", ["query_db"])
    candidate = _trace("trace-b", "scenario-b", ["query_db"])
    diff = _build_diff(baseline, candidate)
    rendered = _to_terminal_text(diff)
    assert "scenarios differ" in rendered

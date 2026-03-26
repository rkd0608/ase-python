"""Trajectory efficiency evaluators for ideal tool-call sequence matching."""

from __future__ import annotations

from collections import Counter
from typing import Any

from ase.evaluation.base import AssertionResult, Evaluator, Pillar
from ase.trace.model import Trace, TraceEventKind


class TrajectoryEvaluator(Evaluator):
    """Compares actual tool call sequence against an ideal trajectory."""

    @property
    def name(self) -> str:
        return "trajectory"

    @property
    def pillar(self) -> Pillar:
        return Pillar.EFFICIENCY

    def evaluate(self, trace: object, params: dict[str, Any], **context: Any) -> AssertionResult:
        del context
        resolved = _trace(trace)
        expected = [str(item) for item in params.get("expected_sequence", [])]
        strict_order = bool(params.get("strict_order", True))
        allow_extra = bool(params.get("allow_extra", False))
        actual = _actual_sequence(resolved)

        if not expected:
            return AssertionResult(
                evaluator=self.name,
                pillar=self.pillar,
                passed=True,
                score=100.0,
                message=(
                    "trajectory check skipped: expected sequence is empty; "
                    f"actual sequence: {actual}"
                ),
                details={"expected_sequence": expected, "actual_sequence": actual},
            )

        matched, missing = _ordered_match(expected, actual)
        extra = max(len(actual) - matched, 0)
        reordered = _reordered_count(expected, actual) if strict_order else 0
        if allow_extra:
            extra = 0

        total_expected = max(len(expected), 1)
        matched_score = matched / total_expected * 100.0
        extra_penalty = extra * 0.5 / total_expected * 100.0
        missing_penalty = missing * 1.0 / total_expected * 100.0
        order_penalty = reordered * 0.25 / total_expected * 100.0
        score = max(0.0, matched_score - extra_penalty - missing_penalty - order_penalty)
        passed = score >= 70.0
        return AssertionResult(
            evaluator=self.name,
            pillar=self.pillar,
            passed=passed,
            score=score,
            message=(
                f"expected={expected}; actual={actual}; matched={matched}; missing={missing}; "
                f"extra={extra}; reordered={reordered}; score={score:.2f}"
            ),
            details={
                "expected_sequence": expected,
                "actual_sequence": actual,
                "matched": matched,
                "missing": missing,
                "extra": extra,
                "reordered": reordered,
            },
        )


def _actual_sequence(trace: Trace) -> list[str]:
    sequence: list[str] = []
    for event in trace.events:
        if event.kind != TraceEventKind.TOOL_CALL or event.tool_call is None:
            continue
        payload = event.tool_call.payload or {}
        name = payload.get("tool_name")
        if isinstance(name, str) and name:
            sequence.append(name)
            continue
        sequence.append(event.tool_call.target)
    return sequence


def _ordered_match(expected: list[str], actual: list[str]) -> tuple[int, int]:
    expected_counts = Counter(expected)
    actual_counts = Counter(actual)
    matched = sum(
        min(expected_counts[name], actual_counts.get(name, 0))
        for name in expected_counts
    )
    missing = sum(
        max(expected_counts[name] - actual_counts.get(name, 0), 0)
        for name in expected_counts
    )
    return matched, missing


def _reordered_count(expected: list[str], actual: list[str]) -> int:
    actual_positions: dict[str, list[int]] = {}
    for index, name in enumerate(actual):
        actual_positions.setdefault(name, []).append(index)
    expected_positions: dict[str, list[int]] = {}
    for index, name in enumerate(expected):
        expected_positions.setdefault(name, []).append(index)
    reordered = 0
    for name, indices in expected_positions.items():
        actual_indices = actual_positions.get(name, [])
        for index, expected_index in enumerate(indices):
            if index >= len(actual_indices):
                continue
            if actual_indices[index] != expected_index:
                reordered += 1
    return reordered


def _trace(value: object) -> Trace:
    if not isinstance(value, Trace):
        raise ValueError("trace must be a Trace instance")
    return value

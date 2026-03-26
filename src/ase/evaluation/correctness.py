"""Correctness evaluators for observable agent behavior.

These evaluators answer the core ASE question: did the agent take the
expected actions against its environment, regardless of the exact text it
produced for a user.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ase.evaluation.base import AssertionOutcome, AssertionResult, Evaluator, Pillar
from ase.trace.model import ToolCallEvent, Trace, TraceEventKind


class ToolCalledEvaluator(Evaluator):
    """Verify that a scenario exercised the expected tool path."""

    @property
    def name(self) -> str:
        return "tool_called"

    @property
    def pillar(self) -> Pillar:
        return Pillar.CORRECTNESS

    def evaluate(self, trace: Trace, params: dict[str, Any], **context: Any) -> AssertionResult:
        del context
        if not isinstance(params, dict):
            return _invalid_params_result(self.name, self.pillar, "params must be a dictionary")
        kind = str(params.get("kind", "")).strip().lower()
        try:
            minimum = max(0, int(params.get("minimum", 1)))
        except (TypeError, ValueError):
            return _invalid_params_result(
                self.name,
                self.pillar,
                "minimum must be an integer",
                params=params,
            )
        method = _optional_upper(params.get("method"))
        target_contains = _optional_lower(params.get("target_contains"))
        matches = _matching_calls(trace, kind, method, target_contains)
        passed = len(matches) >= minimum
        label = kind or "tool"
        return AssertionResult(
            evaluator=self.name,
            pillar=self.pillar,
            passed=passed,
            score=1.0 if passed else 0.0,
            message=_tool_called_message(label, minimum, len(matches), passed),
            outcome=AssertionOutcome.PASS if passed else AssertionOutcome.FAIL,
            details={
                "kind": kind or None,
                "minimum": minimum,
                "actual": len(matches),
                "method": method,
                "target_contains": target_contains,
            },
        )


class APICalledEvaluator(Evaluator):
    """Keep API-call assertions as a neutral alias over the shared tool model."""

    @property
    def name(self) -> str:
        return "api_called"

    @property
    def pillar(self) -> Pillar:
        return Pillar.CORRECTNESS

    def evaluate(self, trace: Trace, params: dict[str, Any], **context: Any) -> AssertionResult:
        tool_params = dict(params)
        tool_params["kind"] = "http_api"
        return ToolCalledEvaluator().evaluate(trace, tool_params, **context).model_copy(
            update={"evaluator": self.name}
        )


def _matching_calls(
    trace: Trace,
    kind: str,
    method: str | None,
    target_contains: str | None,
) -> list[ToolCallEvent]:
    """Filter tool calls using only generic trace-level properties."""
    matches: list[ToolCallEvent] = []
    for event in _events(trace):
        if event.kind != TraceEventKind.TOOL_CALL or event.tool_call is None:
            continue
        if kind and event.tool_call.kind.value != kind:
            continue
        if method and event.tool_call.method.upper() != method:
            continue
        if target_contains and target_contains not in event.tool_call.target.lower():
            continue
        matches.append(event.tool_call)
    return matches


def _events(trace: object) -> list[object]:
    raw = getattr(trace, "events", [])
    if not isinstance(raw, Iterable):
        return []
    return list(raw)


def _optional_upper(value: object) -> str | None:
    """Normalize optional HTTP or tool verbs for equality checks."""
    if value is None:
        return None
    text = str(value).strip()
    return text.upper() if text else None


def _optional_lower(value: object) -> str | None:
    """Normalize optional contains-style filters for case-insensitive matching."""
    if value is None:
        return None
    text = str(value).strip()
    return text.lower() if text else None


def _tool_called_message(
    kind: str,
    minimum: int,
    actual: int,
    passed: bool,
) -> str:
    """Render stable operator-facing messages for correctness assertions."""
    if passed:
        return f"observed {actual} '{kind}' call(s)"
    return f"expected >={minimum} '{kind}' call(s), got {actual}"


def _invalid_params_result(
    evaluator: str,
    pillar: Pillar,
    message: str,
    params: dict[str, Any] | None = None,
) -> AssertionResult:
    return AssertionResult(
        evaluator=evaluator,
        pillar=pillar,
        passed=False,
        score=0.0,
        message=f"invalid params: {message}",
        outcome=AssertionOutcome.ERROR,
        details={"params": dict(params or {})},
    )

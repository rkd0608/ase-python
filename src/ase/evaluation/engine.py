"""Evaluation engine and built-in evaluator registry.

This module keeps ASE's assertion execution generic: scenarios reference
stable evaluator names, while the engine resolves those names to a neutral
plugin registry and computes one aggregate summary.
"""

from __future__ import annotations

from collections.abc import Iterable
from importlib import import_module
from typing import Any

import structlog

from ase.errors import EvaluatorNotFoundError
from ase.evaluation.base import AssertionResult, EvaluationSummary, Evaluator, Pillar
from ase.evaluation.correctness import APICalledEvaluator, ToolCalledEvaluator
from ase.evaluation.scoring import compute_summary
from ase.scenario.model import AssertionConfig
from ase.trace.model import Trace

log = structlog.get_logger(__name__)


class EvaluationEngine:
    """Evaluate scenario assertions against traces using a neutral registry."""

    def __init__(self, evaluators: Iterable[Evaluator] | None = None) -> None:
        self._registry: dict[str, Evaluator] = {}
        for evaluator in evaluators or _builtin_evaluators():
            self.register(evaluator)

    def register(self, evaluator: Evaluator) -> None:
        """Register one evaluator instance under its stable public name."""
        self._registry[evaluator.name] = evaluator

    def evaluate(
        self,
        trace: Trace,
        assertions: list[AssertionConfig],
        context: dict[str, Any] | None = None,
        weights: dict[str, float] | None = None,
    ) -> EvaluationSummary:
        """Run every assertion and return one aggregate evaluation summary."""
        resolved_context = dict(context or {})
        results = [
            self._evaluate_assertion(trace, assertion, resolved_context)
            for assertion in assertions
        ]
        summary = compute_summary(
            trace_id=trace.trace_id,
            scenario_id=trace.scenario_id,
            results=results,
            weights=weights,
        )
        log.info(
            "evaluation_complete",
            scenario=trace.scenario_id,
            passed=summary.passed,
            ase_score=summary.ase_score,
        )
        return summary

    def _evaluate_assertion(
        self,
        trace: Trace,
        assertion: AssertionConfig,
        context: dict[str, Any],
    ) -> AssertionResult:
        """Convert one assertion config into a concrete assertion result."""
        try:
            evaluator = self._registry[assertion.evaluator]
        except KeyError:
            result = _unknown_evaluator_result(assertion)
        else:
            try:
                result = evaluator.evaluate(trace, dict(assertion.params), **context)
            except ValueError as exc:
                raise EvaluatorNotFoundError(
                    f"failed to evaluate {assertion.evaluator}: {exc}"
                ) from exc
        result = _apply_pillar_override(result, assertion.pillar)
        log.debug(
            "assertion_evaluated",
            evaluator=result.evaluator,
            passed=result.passed,
            score=result.score,
        )
        return result


def _builtin_evaluators() -> list[Evaluator]:
    """Return ASE's built-in evaluator set in one neutral registry order."""
    evaluators: list[Evaluator] = [ToolCalledEvaluator(), APICalledEvaluator()]
    evaluators.extend(
        _load_optional_evaluators(
            "ase.evaluation.safety",
            ["NoUnauthorizedAccessEvaluator", "NoPIIEvaluator", "NoRawSQLEvaluator"],
        )
    )
    evaluators.extend(
        _load_optional_evaluators(
            "ase.evaluation.efficiency",
            [
                "MaxToolCallsEvaluator",
                "MaxTokensEvaluator",
                "CostProjectionEvaluator",
                "SolveRateEvaluator",
                "LatencyRatioEvaluator",
                "CostEfficiencyEvaluator",
            ],
        )
    )
    evaluators.extend(
        _load_optional_evaluators(
            "ase.evaluation.trajectory",
            ["TrajectoryEvaluator"],
        )
    )
    evaluators.extend(
        _load_optional_evaluators(
            "ase.evaluation.consistency",
            ["SameToolCallsEvaluator", "SameMetricsEvaluator"],
        )
    )
    evaluators.extend(
        _load_optional_evaluators(
            "ase.evaluation.policy",
            [
                "ApprovalRequiredEvaluator",
                "RequiredApprovalEvaluator",
                "AllowedToolsEvaluator",
                "BlockedToolsEvaluator",
                "AllowedHostsEvaluator",
                "BlockedHostsEvaluator",
                "MaxMutationScopeEvaluator",
                "NoProductionWritesEvaluator",
                "NoDuplicateSideEffectsEvaluator",
                "TrajectoryContainsEvaluator",
                "TrajectoryOrderEvaluator",
                "ExactEmailCountEvaluator",
                "ExactAPICallCountEvaluator",
            ],
        )
    )
    return evaluators


def _unknown_evaluator_result(assertion: AssertionConfig) -> AssertionResult:
    """Return a stable failed result when a scenario references no registry entry."""
    pillar = _parse_pillar(assertion.pillar) or Pillar.CUSTOM
    return AssertionResult(
        evaluator=assertion.evaluator,
        pillar=pillar,
        passed=False,
        score=0.0,
        message=f"unknown evaluator: {assertion.evaluator}",
    )


def _apply_pillar_override(
    result: AssertionResult,
    pillar_name: str | None,
) -> AssertionResult:
    """Let scenarios re-bucket results without changing evaluator plugins."""
    pillar = _parse_pillar(pillar_name)
    if pillar is None:
        return result
    return result.model_copy(update={"pillar": pillar})


def _parse_pillar(pillar_name: str | None) -> Pillar | None:
    """Parse optional pillar overrides without crashing the full run."""
    if not pillar_name:
        return None
    try:
        return Pillar(pillar_name)
    except ValueError:
        return None


def _load_optional_evaluators(module_name: str, class_names: list[str]) -> list[Evaluator]:
    """Load optional evaluator modules without breaking the whole engine."""
    try:
        module = import_module(module_name)
    except ImportError:
        return []
    evaluators: list[Evaluator] = []
    for class_name in class_names:
        evaluator_cls = getattr(module, class_name, None)
        if evaluator_cls is None:
            continue
        evaluators.append(evaluator_cls())
    return evaluators

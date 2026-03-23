"""Aggregate evaluator results into ASE's summary model."""

from __future__ import annotations

from collections import defaultdict

from ase.evaluation.base import AssertionResult, EvaluationSummary, Pillar


def compute_summary(
    trace_id: str,
    scenario_id: str,
    results: list[AssertionResult],
    weights: dict[str, float] | None = None,
) -> EvaluationSummary:
    """Aggregate evaluator results into one deterministic summary object."""
    weights = weights or {}
    if not results:
        pillar_scores = {pillar.value: 1.0 for pillar in Pillar}
        return EvaluationSummary(
            trace_id=trace_id,
            scenario_id=scenario_id,
            passed=True,
            ase_score=1.0,
            total=0,
            passed_count=0,
            failed_count=0,
            results=[],
            pillar_scores=pillar_scores,
            failing_evaluators=[],
        )

    grouped: dict[str, list[float]] = defaultdict(list)
    for result in results:
        grouped[result.pillar.value].append(result.score)
    pillar_scores = {
        pillar.value: _average(grouped.get(pillar.value, [1.0]))
        for pillar in Pillar
    }
    weighted_total = 0.0
    weight_sum = 0.0
    for pillar_name, score in pillar_scores.items():
        weight = float(weights.get(pillar_name, 1.0))
        weighted_total += score * weight
        weight_sum += weight
    ase_score = weighted_total / max(weight_sum, 1.0)
    failing = [result.evaluator for result in results if not result.passed]
    return EvaluationSummary(
        trace_id=trace_id,
        scenario_id=scenario_id,
        passed=not failing,
        ase_score=ase_score,
        total=len(results),
        passed_count=sum(1 for result in results if result.passed),
        failed_count=sum(1 for result in results if not result.passed),
        results=results,
        pillar_scores=pillar_scores,
        failing_evaluators=failing,
    )


def _average(scores: list[float]) -> float:
    """Compute one average score for a pillar bucket."""
    return sum(scores) / max(len(scores), 1)

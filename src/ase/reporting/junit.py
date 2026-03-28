"""JUnit XML output for ASE evaluation summaries and trace fallbacks."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from ase.errors import TraceSerializationError
from ase.evaluation.base import AssertionResult, EvaluationSummary, Pillar
from ase.evaluation.trace_summary import summary_from_trace
from ase.trace.model import Trace


def to_string(summary: EvaluationSummary) -> str:
    """Render one evaluation summary as JUnit XML."""
    suite = ET.Element(
        "testsuite",
        name=summary.scenario_id,
        tests=str(summary.total),
        failures=str(summary.failed_count),
    )
    for result in summary.results:
        case = ET.SubElement(
            suite,
            "testcase",
            classname=summary.scenario_id,
            name=result.evaluator,
        )
        if not result.passed:
            failure = ET.SubElement(case, "failure", message=result.message)
            failure.text = result.message
    return ET.tostring(suite, encoding="unicode")


def write_to_file(summary: EvaluationSummary, path: Path) -> None:
    """Write JUnit XML to disk."""
    try:
        path.write_text(to_string(summary) + "\n", encoding="utf-8")
    except OSError as exc:
        raise TraceSerializationError(f"failed to write JUnit report {path}: {exc}") from exc


def trace_to_string(trace: Trace) -> str:
    """Render one trace as JUnit even when no evaluation summary exists yet."""
    return to_string(_summary_for_trace(trace))


def _summary_for_trace(trace: Trace) -> EvaluationSummary:
    """Fallback to trace status so replay-only traces still export to CI systems."""
    existing = summary_from_trace(trace)
    if existing is not None:
        return existing
    passed = trace.status.value == "passed"
    result = AssertionResult(
        evaluator="trace_status",
        pillar=Pillar.CUSTOM,
        passed=passed,
        score=1.0 if passed else 0.0,
        message=trace.error_message or f"trace status: {trace.status.value}",
    )
    return EvaluationSummary(
        trace_id=trace.trace_id,
        scenario_id=trace.scenario_id,
        passed=passed,
        ase_score=result.score,
        total=1,
        passed_count=1 if passed else 0,
        failed_count=0 if passed else 1,
        results=[result],
        failing_evaluators=[] if passed else ["trace_status"],
    )

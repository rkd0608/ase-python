"""JUnit XML output for ASE evaluation summaries."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from ase.errors import TraceSerializationError
from ase.evaluation.base import EvaluationSummary


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

"""JSON report helpers for ASE evaluation summaries and traces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ase.errors import TraceSerializationError
from ase.evaluation.base import EvaluationSummary
from ase.trace.model import Trace


def summary_dict(summary: EvaluationSummary) -> dict[str, Any]:
    """Convert one evaluation summary into a stable JSON payload."""
    return summary.model_dump(mode="json")


def trace_dict(trace: Trace) -> dict[str, Any]:
    """Convert one trace into a stable JSON payload."""
    return trace.model_dump(mode="json")


def to_string(
    summary: EvaluationSummary | None = None,
    trace: Trace | None = None,
) -> str:
    """Render a summary or trace as pretty JSON."""
    if trace is not None:
        return json.dumps(trace_dict(trace), indent=2)
    if summary is None:
        raise TraceSerializationError("json report requires a summary or trace")
    return json.dumps(summary_dict(summary), indent=2)


def write_to_file(
    path: Path,
    summary: EvaluationSummary | None = None,
    trace: Trace | None = None,
) -> None:
    """Write one JSON report artifact to disk."""
    try:
        path.write_text(to_string(summary=summary, trace=trace) + "\n", encoding="utf-8")
    except OSError as exc:
        raise TraceSerializationError(f"failed to write JSON report {path}: {exc}") from exc

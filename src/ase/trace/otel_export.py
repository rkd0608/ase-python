"""OTEL-like export helpers for ASE traces."""

from __future__ import annotations

import hashlib
from typing import Any

from ase.trace.model import Trace, TraceEventKind


def to_otel_dict(trace: Trace) -> dict[str, Any]:
    """Export one ASE trace into a compact OTEL-like JSON structure."""
    runtime = trace.runtime_provenance
    attributes: dict[str, Any] = {
        "ase.trace_id": trace.trace_id,
        "ase.scenario_id": trace.scenario_id,
        "ase.status": trace.status.value,
        "ase.runtime_mode": runtime.mode if runtime else "unknown",
        "ase.framework": runtime.framework if runtime and runtime.framework else "",
    }
    if trace.evaluation is not None:
        attributes["ase.evaluation.passed"] = trace.evaluation.passed
        attributes["ase.evaluation.score"] = trace.evaluation.ase_score
    spans = [_span_from_event(trace.trace_id, event) for event in trace.events]
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": _kv(attributes)},
                "scopeSpans": [{"scope": {"name": "ase"}, "spans": spans}],
            }
        ]
    }


def _span_from_event(trace_id: str, event: object) -> dict[str, Any]:
    """Convert one ASE event into an OTEL-like span."""
    from ase.trace.model import TraceEvent

    assert isinstance(event, TraceEvent)
    span_name = event.kind.value
    attributes: dict[str, Any] = {"ase.event_id": event.event_id}
    if event.tool_call is not None:
        attributes.update(
            {
                "ase.tool.kind": event.tool_call.kind.value,
                "ase.tool.method": event.tool_call.method,
                "ase.tool.target": event.tool_call.target,
            }
        )
    return {
        "traceId": _hash_hex(trace_id, 32),
        "spanId": _hash_hex(event.event_id, 16),
        "name": span_name,
        "kind": _otel_kind(event.kind),
        "startTimeUnixNano": int(event.timestamp_ms * 1_000_000),
        "endTimeUnixNano": int(event.timestamp_ms * 1_000_000),
        "attributes": _kv(attributes),
    }


def _otel_kind(kind: TraceEventKind) -> int:
    """Map ASE event kinds onto OTEL span kinds."""
    if kind == TraceEventKind.TOOL_CALL:
        return 3
    return 1


def _hash_hex(value: str, length: int) -> str:
    """Generate a deterministic hex identifier of the requested length."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _kv(values: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a flat mapping into OTEL-like key/value attributes."""
    return [{"key": key, "value": {"stringValue": str(value)}} for key, value in values.items()]

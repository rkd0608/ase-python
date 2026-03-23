"""OTEL-like import helpers for ASE traces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ase.errors import OTelImportError
from ase.trace.builder import TraceBuilder
from ase.trace.model import AdapterMetadata, RuntimeProvenance, ToolCallEvent, ToolCallKind, Trace


def read_otel_trace(path: Path) -> Trace:
    """Read one OTEL-like JSON trace and convert it into ASE format."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OTelImportError(f"failed to read OTEL trace {path}: {exc}") from exc
    return trace_from_otel_dict(payload)


def trace_from_otel_dict(data: dict[str, Any]) -> Trace:
    """Convert OTEL-like JSON into a native ASE trace."""
    try:
        resource_span = data["resourceSpans"][0]
        scope_span = resource_span["scopeSpans"][0]
        spans = scope_span.get("spans", [])
    except (KeyError, IndexError, TypeError) as exc:
        raise OTelImportError(f"invalid OTEL payload: {exc}") from exc
    attrs = _attr_map(resource_span.get("resource", {}).get("attributes", []))
    builder = TraceBuilder(
        scenario_id=attrs.get("ase.scenario_id", "otel-import"),
        scenario_name=attrs.get("ase.scenario_id", "otel-import"),
    )
    builder.set_runtime_provenance(
        mode=attrs.get("ase.runtime_mode", "imported"),
        framework=attrs.get("ase.framework") or None,
    )
    trace = builder.current_trace
    trace.adapter_metadata = AdapterMetadata(
        name="otel-import",
        transport="otel-json",
        framework=attrs.get("ase.framework") or None,
        source="otel-import",
    )
    trace.runtime_provenance = RuntimeProvenance(
        mode=attrs.get("ase.runtime_mode", "imported"),
        framework=attrs.get("ase.framework") or None,
        event_source="otel-json",
    )
    for span in spans:
        span_attrs = _attr_map(span.get("attributes", []))
        if "ase.tool.kind" not in span_attrs:
            continue
        builder.add_tool_call(
            ToolCallEvent(
                kind=_tool_kind(span_attrs.get("ase.tool.kind")),
                method=span_attrs.get("ase.tool.method", "UNKNOWN"),
                target=span_attrs.get("ase.tool.target", "unknown"),
            )
        )
    return builder.finish()


def _attr_map(attributes: list[dict[str, Any]]) -> dict[str, str]:
    """Convert OTEL-like key/value attributes into a plain mapping."""
    values: dict[str, str] = {}
    for item in attributes:
        key = item.get("key")
        value = item.get("value", {})
        if key is None:
            continue
        values[str(key)] = _attribute_value(value)
    return values


def _tool_kind(value: str | None) -> ToolCallKind:
    """Parse imported tool kinds without crashing the full import."""
    try:
        return ToolCallKind(value or ToolCallKind.UNKNOWN.value)
    except ValueError:
        return ToolCallKind.UNKNOWN


def _attribute_value(value: dict[str, Any]) -> str:
    """Read OTEL-like scalar values without losing string attributes."""
    if "stringValue" in value:
        return str(value["stringValue"])
    if "boolValue" in value:
        return str(value["boolValue"])
    if "intValue" in value:
        return str(value["intValue"])
    if "doubleValue" in value:
        return str(value["doubleValue"])
    return ""

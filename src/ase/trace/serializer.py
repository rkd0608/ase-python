"""JSON serialization helpers for native ASE traces."""

from __future__ import annotations

import json
from pathlib import Path

from ase.errors import TraceSchemaMigrationError, TraceSerializationError
from ase.trace.model import TRACE_SCHEMA_VERSION, Trace


def serialize(trace: Trace) -> str:
    """Serialize one trace to stable JSON."""
    try:
        return json.dumps(trace.model_dump(mode="json"), indent=2)
    except Exception as exc:  # noqa: BLE001
        raise TraceSerializationError(f"failed to serialize trace {trace.trace_id}: {exc}") from exc


def deserialize(raw: str) -> Trace:
    """Parse one trace from native JSON."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TraceSerializationError(f"failed to parse trace JSON: {exc}") from exc
    schema_version = payload.get("schema_version", TRACE_SCHEMA_VERSION)
    if schema_version > TRACE_SCHEMA_VERSION:
        raise TraceSchemaMigrationError(
            f"trace schema {schema_version} is newer than supported {TRACE_SCHEMA_VERSION}"
        )
    try:
        return Trace.model_validate(payload)
    except Exception as exc:  # noqa: BLE001
        raise TraceSerializationError(f"failed to validate trace payload: {exc}") from exc


def read_from_file(path: Path) -> Trace:
    """Read one native trace from disk."""
    try:
        return deserialize(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TraceSerializationError(f"failed to read trace file {path}: {exc}") from exc


def write_to_file(trace: Trace, path: Path) -> None:
    """Write one native trace to disk."""
    try:
        path.write_text(serialize(trace) + "\n", encoding="utf-8")
    except OSError as exc:
        raise TraceSerializationError(f"failed to write trace file {path}: {exc}") from exc

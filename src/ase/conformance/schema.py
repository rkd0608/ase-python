"""Schema validation helpers for conformance manifests and results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from ase.errors import ConformanceError

_SCHEMAS = Path(__file__).resolve().parents[3] / "schemas"


def validate_manifest_dict(data: dict[str, Any], source: str) -> None:
    """Validate a conformance manifest payload against the public schema."""
    _validate(data, _SCHEMAS / "ase_conformance_manifest.schema.json", source)


def validate_result_dict(data: dict[str, Any], source: str) -> None:
    """Validate a conformance result payload against the public schema."""
    _validate(data, _SCHEMAS / "ase_conformance_result.schema.json", source)


def _validate(data: dict[str, Any], schema_path: Path, source: str) -> None:
    """Load one schema file and raise contextual validation errors."""
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConformanceError(f"failed to read schema {schema_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConformanceError(f"invalid schema {schema_path}: {exc}") from exc
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as exc:
        raise ConformanceError(f"schema validation failed for {source}: {exc.message}") from exc

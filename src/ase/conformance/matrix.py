"""Compatibility matrix helpers built from certification result artifacts."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from pydantic import BaseModel

from ase.conformance.model import ConformanceResult
from ase.errors import ConformanceError


class CompatibilityRow(BaseModel):
    """One row in the generated compatibility matrix."""

    framework: str
    language: str
    adapter_name: str
    adapter_version: str
    bundle_family: str
    certification_level: str
    bundle_version: str
    passed: bool
    generated_at: str
    source_artifact: str


class CertificationArtifact(BaseModel):
    """One validated certification artifact paired with its source path."""

    path: str
    result: ConformanceResult


def load_results(paths: list[Path]) -> list[CertificationArtifact]:
    """Load certification results from JSON files and directories."""
    return [load_result(path) for path in _expand_result_paths(paths)]


def load_result(path: Path) -> CertificationArtifact:
    """Load one certification result artifact from disk."""
    if not path.exists():
        raise ConformanceError(f"certification result not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConformanceError(f"failed to read certification result {path}: {exc}") from exc
    try:
        result = ConformanceResult.model_validate(payload)
    except Exception as exc:
        raise ConformanceError(f"failed to validate certification result {path}: {exc}") from exc
    return CertificationArtifact(path=str(path), result=result)


def build_rows(artifacts: list[CertificationArtifact]) -> list[CompatibilityRow]:
    """Convert certification results into sorted matrix rows."""
    rows = [
        CompatibilityRow(
            framework=artifact.result.framework or "unknown",
            language=artifact.result.language or "unknown",
            adapter_name=artifact.result.adapter_name,
            adapter_version=artifact.result.adapter_version or "unspecified",
            bundle_family=artifact.result.bundle_family,
            certification_level=artifact.result.certification_level.value,
            bundle_version=artifact.result.bundle_version,
            passed=artifact.result.passed,
            generated_at=_format_generated_at(artifact.result.generated_at_ms),
            source_artifact=artifact.path,
        )
        for artifact in artifacts
    ]
    return sorted(rows, key=lambda row: (row.framework, row.language, row.adapter_name))


def to_markdown(rows: list[CompatibilityRow]) -> str:
    """Render a compatibility matrix as a Markdown table."""
    header = (
        "| Framework | Language | Adapter | Adapter Version | Bundle Family | Level | "
        "Bundle | Status | Generated | Artifact |\n"
        "|---|---|---|---|---|---|---|---|---|---|"
    )
    body = [
        "| "
        f"{row.framework} | {row.language} | {row.adapter_name} | {row.adapter_version} | "
        f"{row.bundle_family} | {row.certification_level} | {row.bundle_version} | "
        f"{'certified' if row.passed else 'failing'} | {row.generated_at} | {row.source_artifact} |"
        for row in rows
    ]
    return "\n".join([header, *body])


def _expand_result_paths(paths: list[Path]) -> list[Path]:
    """Accept both artifact files and downloaded-artifact directories."""
    expanded: list[Path] = []
    for path in paths:
        if path.is_dir():
            expanded.extend(sorted(path.rglob("*.cert.json")))
        else:
            expanded.append(path)
    if not expanded:
        raise ConformanceError("no certification result artifacts found")
    return expanded


def _format_generated_at(ms: float) -> str:
    """Render artifact generation time as an ISO-like UTC timestamp."""
    return datetime.datetime.fromtimestamp(ms / 1000, datetime.UTC).strftime(
        "%Y-%m-%d %H:%M:%SZ"
    )

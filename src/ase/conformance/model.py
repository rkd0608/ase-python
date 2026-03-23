"""Models for ASE adapter conformance manifests and certification output."""

from __future__ import annotations

import time
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

CONFORMANCE_SPEC_VERSION = 1


class CertificationLevel(StrEnum):
    """Define public certification tiers without scenario-model imports."""

    CORE = "core"
    STATEFUL = "stateful"
    MULTI_AGENT = "multi_agent"
    MCP = "mcp"
    REALTIME = "realtime"


class ConformanceCase(BaseModel):
    """Describe one reusable certification case inside a conformance bundle."""

    case_id: str
    name: str
    adapter_events: str
    scenario: str | None = None
    required_event_types: list[str] = Field(default_factory=list)
    required_protocols: list[str] = Field(default_factory=list)
    minimum_fidelity: dict[str, int] = Field(default_factory=dict)
    methodology_profiles: list[str] = Field(default_factory=list)


class ConformanceManifest(BaseModel):
    """Describe one language-neutral certification manifest."""

    spec_version: int = CONFORMANCE_SPEC_VERSION
    manifest_id: str
    name: str
    adapter_name: str
    adapter_version: str | None = None
    bundle_family: str = "launch"
    bundle_version: str = "1.0.0"
    framework: str | None = None
    language: str | None = None
    certification_target: CertificationLevel = CertificationLevel.CORE
    methodology_profiles: list[str] = Field(default_factory=lambda: ["core"])
    cases: list[ConformanceCase] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConformanceCheckResult(BaseModel):
    """Capture one pass/fail check inside a certification run."""

    check_id: str
    case_id: str
    passed: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ConformanceResult(BaseModel):
    """Represent one certification result emitted by `ase certify`."""

    spec_version: int = CONFORMANCE_SPEC_VERSION
    manifest_id: str
    manifest_name: str
    adapter_name: str
    adapter_version: str | None = None
    bundle_family: str = "launch"
    bundle_version: str = "1.0.0"
    framework: str | None = None
    language: str | None = None
    certification_level: CertificationLevel
    passed: bool
    methodology_profiles: list[str] = Field(default_factory=list)
    checks: list[ConformanceCheckResult] = Field(default_factory=list)
    generated_at_ms: float = Field(default_factory=lambda: time.time() * 1000)
    report_digest_sha256: str | None = None
    signature_algorithm: str | None = None
    signature: str | None = None


def resolve_case_path(manifest_path: Path, relative_path: str) -> Path:
    """Resolve case-local paths relative to the manifest file location."""
    path = Path(relative_path)
    return path if path.is_absolute() else manifest_path.resolve().parent / path

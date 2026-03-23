"""Tests for compatibility-matrix generation from certification artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ase.conformance.matrix import build_rows, load_results, to_markdown
from ase.errors import ConformanceError


def _write_artifact(path: Path, *, manifest_id: str, passed: bool = True) -> None:
    """Write one minimal valid certification result artifact for matrix tests."""
    path.write_text(
        json.dumps(
            {
                "spec_version": 1,
                "manifest_id": manifest_id,
                "manifest_name": "Example Bundle",
                "adapter_name": "openai-agents-python",
                "adapter_version": "1.0.0",
                "bundle_family": "core",
                "bundle_version": "1.0.0",
                "framework": "openai-agents",
                "language": "python",
                "certification_level": "core",
                "passed": passed,
                "methodology_profiles": ["core"],
                "checks": [],
                "generated_at_ms": 1_700_000_000_000.0,
                "report_digest_sha256": "abc",
            }
        ),
        encoding="utf-8",
    )


def test_load_results_supports_directories(tmp_path: Path) -> None:
    artifact = tmp_path / "openai.cert.json"
    _write_artifact(artifact, manifest_id="m1")
    loaded = load_results([tmp_path])
    rows = build_rows(loaded)
    assert len(rows) == 1
    assert rows[0].source_artifact.endswith("openai.cert.json")


def test_markdown_includes_artifact_path_and_status(tmp_path: Path) -> None:
    artifact = tmp_path / "openai.cert.json"
    _write_artifact(artifact, manifest_id="m2", passed=False)
    markdown = to_markdown(build_rows(load_results([artifact])))
    assert "openai.cert.json" in markdown
    assert "failing" in markdown


def test_load_results_requires_at_least_one_artifact(tmp_path: Path) -> None:
    with pytest.raises(ConformanceError, match="no certification result artifacts found"):
        load_results([tmp_path])

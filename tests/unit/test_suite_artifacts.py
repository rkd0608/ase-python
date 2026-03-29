from __future__ import annotations

import asyncio
import json
from pathlib import Path

from typer.testing import CliRunner

from ase.cli.main import app
from ase.storage.trace_store import TraceStore
from ase.trace.builder import TraceBuilder

runner = CliRunner()


def _write_scenario(path: Path, scenario_id: str, python_code: str) -> Path:
    path.write_text(
        "\n".join(
            [
                "spec_version: 1",
                f"scenario_id: {scenario_id}",
                f"name: {scenario_id}",
                "agent:",
                "  command:",
                "    - python",
                "    - -c",
                f"    - '{python_code}'",
                "assertions: []",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_test_command_writes_suite_outputs_and_bundle(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "traces.db"
    monkeypatch.setattr(TraceStore, "_DEFAULT_PATH", db_path)
    scenario = _write_scenario(tmp_path / "scenario.yaml", "suite-pass", 'print("ok")')
    out_file = tmp_path / "summary.json"
    bundle_dir = tmp_path / "bundle"

    result = runner.invoke(
        app,
        [
            "test",
            str(scenario),
            "--output",
            "json",
            "--out-file",
            str(out_file),
            "--artifacts-dir",
            str(bundle_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["total_scenarios"] == 1
    assert payload["passed_scenarios"] == 1
    assert (bundle_dir / "summary.json").exists()
    assert (bundle_dir / "report.md").exists()
    assert (bundle_dir / "report.txt").exists()
    assert (bundle_dir / "junit.xml").exists()
    assert (bundle_dir / "trace.json").exists()

    report_result = runner.invoke(app, ["report", str(bundle_dir), "--output", "markdown"])
    assert report_result.exit_code == 0, report_result.output
    assert "# ASE Test Suite Artifact" in report_result.output

    junit_result = runner.invoke(app, ["report", str(bundle_dir), "--output", "junit"])
    assert junit_result.exit_code == 0, junit_result.output
    expected_junit = (bundle_dir / "junit.xml").read_text(encoding="utf-8").strip()
    assert junit_result.output.strip() == expected_junit


def test_compare_accepts_single_scenario_artifact_directories(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "traces.db"
    monkeypatch.setattr(TraceStore, "_DEFAULT_PATH", db_path)
    scenario = _write_scenario(tmp_path / "scenario.yaml", "compare-pass", 'print("ok")')
    bundle_a = tmp_path / "bundle-a"
    bundle_b = tmp_path / "bundle-b"

    first = runner.invoke(app, ["test", str(scenario), "--artifacts-dir", str(bundle_a)])
    second = runner.invoke(app, ["test", str(scenario), "--artifacts-dir", str(bundle_b)])

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output

    result = runner.invoke(app, ["compare", str(bundle_a), str(bundle_b), "--output", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "baseline_trace_id" in payload
    assert payload["scenario_ids"] == ["compare-pass", "compare-pass"]


def test_compare_to_baseline_flags_regression(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "traces.db"
    monkeypatch.setattr(TraceStore, "_DEFAULT_PATH", db_path)

    async def seed_baseline() -> str:
        store = TraceStore(db_path=db_path)
        await store.setup()
        trace = (
            TraceBuilder("regression-scenario", "regression-scenario")
            .set_runtime_provenance(mode="direct", framework="custom")
            .finish()
        )
        await store.save_trace(trace, ase_score=1.0)
        await store.set_baseline("regression-scenario", trace.trace_id)
        await store.close()
        return trace.trace_id

    baseline_trace_id = asyncio.run(seed_baseline())
    scenario = _write_scenario(
        tmp_path / "regression.yaml",
        "regression-scenario",
        "import sys; sys.exit(1)",
    )

    result = runner.invoke(app, ["test", str(scenario), "--compare-to-baseline"])
    assert result.exit_code != 0, result.output
    assert f"Regression vs baseline {baseline_trace_id}" in result.output
    assert "This run regressed against the pinned baseline." in result.output

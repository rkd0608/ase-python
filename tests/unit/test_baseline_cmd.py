from __future__ import annotations

import asyncio
from pathlib import Path

from rich.console import Console
from typer.testing import CliRunner

from ase.cli import baseline_cmd
from ase.storage.trace_store import TraceStore
from ase.trace.builder import TraceBuilder
from ase.trace.model import ToolCallEvent, ToolCallKind

runner = CliRunner()


def _seed_trace(store_path: Path) -> str:
    async def run() -> str:
        store = TraceStore(db_path=store_path)
        await store.setup()
        trace = (
            TraceBuilder("scenario-baseline", "Scenario Baseline")
            .set_runtime_provenance(mode="adapter", framework="browser-use")
            .add_tool_call(
                ToolCallEvent(
                    kind=ToolCallKind.HTTP_API,
                    method="GET",
                    target="https://api.example.com/status",
                )
            )
            .finish()
        )
        await store.save_trace(trace)
        await store.close()
        return trace.trace_id

    return asyncio.run(run())


def test_baseline_cli_round_trip(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "traces.db"
    monkeypatch.setattr(TraceStore, "_DEFAULT_PATH", db_path)
    monkeypatch.setattr(baseline_cmd, "_console", Console(force_terminal=False, width=160))
    trace_id = _seed_trace(db_path)

    result = runner.invoke(
        baseline_cmd.app,
        ["set", "--scenario", "scenario-baseline", "--trace-id", trace_id],
    )
    assert result.exit_code == 0, result.output
    assert "Baseline set for scenario-baseline" in result.output
    assert "Checks:     unknown" in result.output

    result = runner.invoke(baseline_cmd.app, ["get", "--scenario", "scenario-baseline"])
    assert result.exit_code == 0, result.output
    assert "Scenario: scenario-baseline" in result.output
    assert f"Trace ID:   {trace_id}" in result.output
    assert "Run result: passed" in result.output
    assert "Checks:     unknown" in result.output
    assert "Framework:  browser-use" in result.output

    result = runner.invoke(baseline_cmd.app, ["list"])
    assert result.exit_code == 0, result.output
    assert "ASE Baselines" in result.output
    assert "scenario-baseline" in result.output
    assert "unknown" in result.output
    assert "browser-use" in result.output

    result = runner.invoke(
        baseline_cmd.app,
        ["clear", "--scenario", "scenario-baseline"],
    )
    assert result.exit_code == 0, result.output
    assert "Removed 1 baseline(s) for scenario-baseline." in result.output


def test_baseline_cli_rejects_mismatched_scenario(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "traces.db"
    monkeypatch.setattr(TraceStore, "_DEFAULT_PATH", db_path)
    trace_id = _seed_trace(db_path)

    result = runner.invoke(
        baseline_cmd.app,
        ["set", "--scenario", "other-scenario", "--trace-id", trace_id],
    )
    assert result.exit_code != 0, result.output
    assert "baseline scenario mismatch" in result.output

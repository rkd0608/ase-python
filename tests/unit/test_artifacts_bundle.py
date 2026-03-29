from __future__ import annotations

import asyncio
import io
import json
from functools import partial
from pathlib import Path
from types import SimpleNamespace

from rich.console import Console

from ase.artifacts.bundle import (
    build_suite_artifact,
    render_json,
    render_junit,
    render_markdown,
    render_terminal,
    scenario_artifact_from_run,
    trace_relative_path,
    write_bundle,
)
from ase.cli import compare as compare_module
from ase.cli import report as report_module
from ase.cli import test_cmd
from ase.config.model import OutputFormat
from ase.evaluation.base import EvaluationSummary
from ase.evaluation.trace_summary import attach_summary
from ase.storage.trace_store import TraceStore
from ase.trace.model import RuntimeProvenance, Trace, TraceEvaluation, TraceMetrics, TraceStatus


def _trace(
    trace_id: str,
    scenario_id: str,
    *,
    passed: bool = True,
    score: float = 1.0,
    error_message: str | None = None,
) -> Trace:
    trace = Trace(
        trace_id=trace_id,
        scenario_id=scenario_id,
        scenario_name=scenario_id,
        status=TraceStatus.PASSED if passed else TraceStatus.FAILED,
        metrics=TraceMetrics(total_tool_calls=1, total_llm_calls=0, total_tokens_used=1),
        runtime_provenance=RuntimeProvenance(mode="adapter", framework="browser-use"),
        error_message=error_message,
    )
    trace.evaluation = TraceEvaluation(
        passed=passed,
        ase_score=score,
        total=2,
        passed_count=2 if passed else 1,
        failed_count=0 if passed else 1,
        failing_evaluators=[] if passed else ["tool_called"],
    )
    return trace


def _summary(trace: Trace) -> EvaluationSummary:
    assert trace.evaluation is not None
    return EvaluationSummary(
        trace_id=trace.trace_id,
        scenario_id=trace.scenario_id,
        passed=trace.evaluation.passed,
        ase_score=trace.evaluation.ase_score,
        total=trace.evaluation.total,
        passed_count=trace.evaluation.passed_count,
        failed_count=trace.evaluation.failed_count,
        failing_evaluators=list(trace.evaluation.failing_evaluators),
    )


def test_test_cmd_writes_artifact_bundle(tmp_path: Path, monkeypatch) -> None:
    scenario = tmp_path / "scenario.yaml"
    scenario.write_text(
        "\n".join(
            [
                "spec_version: 1",
                "scenario_id: bundle-demo",
                "name: Bundle Demo",
                "agent:",
                "  command: ['python3', '-c', 'print(\"ok\")']",
                "assertions: []",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "traces.db"
    monkeypatch.setattr(test_cmd, "TraceStore", partial(TraceStore, db_path))
    buffer = io.StringIO()
    monkeypatch.setattr(test_cmd, "_console", Console(file=buffer, force_terminal=False, width=140))
    bundle_dir = tmp_path / "bundle"

    test_cmd.run([scenario], output=OutputFormat.JSON, out_file=bundle_dir)

    assert buffer.getvalue() == ""
    summary = json.loads((bundle_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["bundle_version"] == 1
    assert summary["run_result"] == "passed"
    assert summary["total_scenarios"] == 1
    assert summary["scenarios"][0]["execution_status"] == "passed"
    assert summary["scenarios"][0]["trace_path"].endswith("trace.json")
    assert (bundle_dir / "report.md").exists()
    assert (bundle_dir / "report.txt").exists()
    assert (bundle_dir / "junit.xml").exists()
    assert (bundle_dir / "trace.json").exists()


def test_bundle_renderers_are_stable(tmp_path: Path) -> None:
    trace = _trace("trace-a", "bundle-scenario")
    summary = _summary(trace)
    attach_summary(trace, summary)
    suite = build_suite_artifact(
        suite_id="suite-a",
        roots=[tmp_path / "scenario.yaml"],
        output_format=OutputFormat.JSON,
        scenarios=[
            scenario_artifact_from_run(
                scenario_path=tmp_path / "scenario.yaml",
                trace=trace,
                trace_id=trace.trace_id,
                trace_path=trace_relative_path(trace.scenario_id),
                execution_status="passed",
                run_result="passed",
                ase_checks="passed (2/2)",
                ase_score=1.0,
                run_type="adapter",
                framework="browser-use",
                tool_calls=1,
                llm_calls=0,
                main_reason=None,
            )
        ],
    )
    rendered_json = render_json(suite)
    rendered_md = render_markdown(suite)
    rendered_txt = render_terminal(suite)
    rendered_junit = render_junit(suite, {trace.trace_id: trace})
    assert '"bundle_version": 1' in rendered_json
    assert "ASE Test Suite Artifact" in rendered_md
    assert "run_result: passed" in rendered_txt
    assert "<testsuite" in rendered_junit


def test_report_and_compare_resolve_bundle_trace_json(tmp_path: Path) -> None:
    trace = _trace("trace-b", "bundle-trace")
    summary = _summary(trace)
    attach_summary(trace, summary)
    suite = build_suite_artifact(
        suite_id="suite-b",
        roots=[tmp_path / "scenario.yaml"],
        output_format=OutputFormat.JSON,
        scenarios=[
            scenario_artifact_from_run(
                scenario_path=tmp_path / "scenario.yaml",
                trace=trace,
                trace_id=trace.trace_id,
                trace_path=trace_relative_path(trace.scenario_id),
                execution_status="passed",
                run_result="passed",
                ase_checks="passed (2/2)",
                ase_score=1.0,
                run_type="adapter",
                framework="browser-use",
                tool_calls=1,
                llm_calls=0,
                main_reason=None,
            )
        ],
    )
    bundle_dir = tmp_path / "bundle"
    write_bundle(bundle_dir, suite, {trace.trace_id: trace})

    loaded_report = report_module._load_trace(bundle_dir)
    loaded_compare = compare_module._load_trace(bundle_dir)
    assert loaded_report.trace_id == trace.trace_id
    assert loaded_compare.trace_id == trace.trace_id
    assert "- Run result:" in report_module._render_trace(loaded_report, OutputFormat.MARKDOWN)


def test_compare_to_baseline_detects_regression(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "traces.db"
    store = TraceStore(db_path)
    asyncio.run(store.setup())
    try:
        baseline = _trace("trace-baseline", "regression-scenario", passed=True, score=1.0)
        current = _trace(
            "trace-current",
            "regression-scenario",
            passed=False,
            score=0.8,
            error_message="browser-use judge rejected result",
        )
        asyncio.run(store.save_trace(baseline))
        asyncio.run(store.set_baseline("regression-scenario", baseline.trace_id))
        scenario = SimpleNamespace(baselines=object(), scenario_id="regression-scenario")
        baseline_trace_id, regression, summary = test_cmd._compare_to_baseline(
            scenario=scenario,
            trace=current,
            summary=_summary(current),
            store=store,
        )
    finally:
        asyncio.run(store.close())
    assert baseline_trace_id == baseline.trace_id
    assert regression is True
    assert "baseline" in summary

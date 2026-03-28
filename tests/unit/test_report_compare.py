from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from ase.config.model import OutputFormat
from ase.trace.model import RuntimeProvenance, Trace, TraceEvaluation, TraceMetrics, TraceStatus

ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


report_module = _load_module("ase_cli_report_source", "src/ase/cli/report.py")
compare_module = _load_module("ase_cli_compare_source", "src/ase/cli/compare.py")


def _trace(trace_id: str, scenario_id: str, *, score: float, passed: bool) -> Trace:
    return Trace(
        trace_id=trace_id,
        scenario_id=scenario_id,
        scenario_name=scenario_id,
        status=TraceStatus.PASSED if passed else TraceStatus.FAILED,
        metrics=TraceMetrics(total_tool_calls=1, total_tokens_used=10),
        runtime_provenance=RuntimeProvenance(mode="adapter", framework="openai-agents"),
        evaluation=TraceEvaluation(
            passed=passed,
            ase_score=score,
            total=2,
            passed_count=1 if not passed else 2,
            failed_count=1 if not passed else 0,
            failing_evaluators=[] if passed else ["tool_called"],
        ),
        error_message=None if passed else "browser-use judge rejected result",
    )


def test_report_renders_terminal_summary() -> None:
    trace = _trace("trace-a", "scenario-a", score=1.0, passed=True)
    rendered = report_module._render_trace(trace, OutputFormat.TERMINAL)
    assert "trace_id: trace-a" in rendered
    assert "runtime_mode: adapter" in rendered
    assert "ase_score: 1.00" in rendered
    assert "execution: passed" in rendered
    assert "evaluation: passed" in rendered


def test_report_renders_failure_reason_in_terminal_and_markdown() -> None:
    trace = _trace("trace-b", "scenario-b", score=0.5, passed=False)
    terminal = report_module._render_trace(trace, OutputFormat.TERMINAL)
    markdown = report_module._render_trace(trace, OutputFormat.MARKDOWN)
    assert "execution: failed" in terminal
    assert "evaluation: failed" in terminal
    assert "error_message: browser-use judge rejected result" in terminal
    assert "- Execution: `failed`" in markdown
    assert "- Evaluation: `failed`" in markdown
    assert "- Error: `browser-use judge rejected result`" in markdown


def test_report_renders_otel_json() -> None:
    trace = _trace("trace-a", "scenario-a", score=1.0, passed=True)
    rendered = report_module._render_trace(trace, OutputFormat.OTEL_JSON)
    payload = json.loads(rendered)
    assert "resourceSpans" in payload


def test_report_renders_junit_without_evaluation() -> None:
    trace = Trace(
        trace_id="trace-a",
        scenario_id="scenario-a",
        scenario_name="scenario-a",
        status=TraceStatus.PASSED,
        metrics=TraceMetrics(total_tool_calls=1, total_tokens_used=10),
        runtime_provenance=RuntimeProvenance(mode="adapter", framework="openai-agents"),
    )
    rendered = report_module._render_trace(trace, OutputFormat.JUNIT)
    assert "<testsuite" in rendered
    assert 'name="scenario-a"' in rendered
    assert "trace_status" in rendered


def test_compare_builds_evaluation_delta() -> None:
    baseline = _trace("trace-a", "scenario-a", score=0.5, passed=False)
    candidate = _trace("trace-b", "scenario-a", score=1.0, passed=True)
    diff = compare_module._build_diff(baseline, candidate)
    assert diff["evaluation_passed"] == [False, True]
    assert diff["ase_score_delta"] == 0.5
    assert diff["failing_evaluators_removed"] == ["tool_called"]

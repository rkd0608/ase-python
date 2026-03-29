from __future__ import annotations

import asyncio
import importlib.util
import io
from pathlib import Path

from rich.console import Console

from ase.trace.model import RuntimeProvenance, Trace, TraceEvaluation, TraceMetrics, TraceStatus

ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


history_module = _load_module("ase_cli_history_source", "src/ase/cli/history_cmd.py")


def _trace(trace_id: str) -> Trace:
    return Trace(
        trace_id=trace_id,
        scenario_id="browser-use-openai-github-trending-first-repo",
        scenario_name="Browser Use OpenAI GitHub Trending First Repo",
        status=TraceStatus.FAILED,
        metrics=TraceMetrics(total_tool_calls=1, total_tokens_used=10),
        runtime_provenance=RuntimeProvenance(mode="adapter", framework="browser-use"),
        evaluation=TraceEvaluation(
            passed=True,
            ase_score=1.0,
            total=2,
            passed_count=2,
            failed_count=0,
        ),
        error_message="browser-use judge rejected result",
    )


class _Store:
    def __init__(self, trace: Trace) -> None:
        self._trace = trace

    async def get_trace(self, trace_id: str) -> Trace | None:
        return self._trace if trace_id == self._trace.trace_id else None

    async def list_traces(
        self,
        scenario_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        del scenario_id, status, limit
        return [
            {
                "trace_id": self._trace.trace_id,
                "scenario_id": self._trace.scenario_id,
                "runtime_mode": (
                    self._trace.runtime_provenance.mode
                    if self._trace.runtime_provenance
                    else None
                ),
                "framework": (
                    self._trace.runtime_provenance.framework
                    if self._trace.runtime_provenance
                    else None
                ),
                "evaluation_status": "passed",
                "status": self._trace.status.value,
                "certification_level": None,
                "ase_score": 1.0,
                "started_at_ms": self._trace.started_at_ms,
            }
        ]


def test_history_show_trace_uses_user_facing_labels() -> None:
    trace = _trace("trace-history-a")
    store = _Store(trace)
    buffer = io.StringIO()
    original_console = history_module._console
    try:
        history_module._console = Console(file=buffer, force_terminal=False, width=160)
        asyncio.run(history_module._show_trace(store, trace.trace_id))
    finally:
        history_module._console = original_console
    output = buffer.getvalue()
    assert "Run: trace-history-a" in output
    assert "Run result: failed" in output
    assert "ASE checks: passed" in output
    assert "Run type:   adapter" in output
    assert "Framework:  browser-use" in output
    assert "What happened:" in output


def test_history_list_traces_keeps_framework_and_run_type_separate() -> None:
    trace = _trace("trace-history-b")
    store = _Store(trace)
    buffer = io.StringIO()
    original_console = history_module._console
    try:
        history_module._console = Console(file=buffer, force_terminal=False, width=160)
        asyncio.run(history_module._list_traces(store, scenario=None, status=None, limit=5))
    finally:
        history_module._console = original_console
    output = buffer.getvalue()
    assert "Run type" in output
    assert "Framework" in output
    assert "ASE checks" in output
    assert "adapter" in output
    assert "browser-use" in output

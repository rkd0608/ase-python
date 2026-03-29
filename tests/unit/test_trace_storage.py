from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

from ase.storage.trace_store import TraceStore
from ase.trace.builder import TraceBuilder
from ase.trace.model import ToolCallEvent, ToolCallKind, TraceEvaluation
from ase.trace.otel_export import to_otel_dict
from ase.trace.otel_import import trace_from_otel_dict
from ase.trace.serializer import deserialize, serialize


def test_trace_serializer_round_trip() -> None:
    trace = (
        TraceBuilder("scenario-roundtrip", "Scenario Roundtrip")
        .add_tool_call(
            ToolCallEvent(kind=ToolCallKind.HTTP_API, method="GET", target="https://api.example.com/orders")
        )
        .finish()
    )
    restored = deserialize(serialize(trace))
    assert restored.trace_id == trace.trace_id
    assert restored.metrics.total_tool_calls == 1


def test_otel_round_trip_preserves_trace_shape() -> None:
    trace = (
        TraceBuilder("scenario-otel", "Scenario OTel")
        .set_runtime_provenance(mode="adapter", framework="openai-agents")
        .add_tool_call(
            ToolCallEvent(kind=ToolCallKind.HTTP_API, method="POST", target="https://api.example.com/refunds")
        )
        .finish()
    )
    imported = trace_from_otel_dict(to_otel_dict(trace))
    assert imported.scenario_id == "scenario-otel"
    assert imported.metrics.total_tool_calls == 1
    assert imported.runtime_provenance is not None
    assert imported.runtime_provenance.framework == "openai-agents"


def test_trace_store_save_and_list(tmp_path: Path) -> None:
    async def run() -> None:
        store = TraceStore(db_path=tmp_path / "traces.db")
        await store.setup()
        trace = (
            TraceBuilder("scenario-store", "Scenario Store")
            .set_runtime_provenance(mode="adapter", framework="langgraph")
            .add_tool_call(
                ToolCallEvent(kind=ToolCallKind.HTTP_API, method="GET", target="https://api.example.com/status")
            )
            .finish()
        )
        await store.save_trace(trace)
        rows = await store.list_traces(scenario_id="scenario-store", limit=1)
        stored = await store.get_trace(trace.trace_id)
        await store.close()
        assert len(rows) == 1
        assert rows[0]["runtime_mode"] == "adapter"
        assert rows[0]["framework"] == "langgraph"
        assert stored is not None
        assert stored.trace_id == trace.trace_id

    asyncio.run(run())


def test_trace_store_baseline_round_trip(tmp_path: Path) -> None:
    async def run() -> None:
        store = TraceStore(db_path=tmp_path / "traces.db")
        await store.setup()
        trace = (
            TraceBuilder("scenario-baseline", "Scenario Baseline")
            .set_runtime_provenance(mode="adapter", framework="browser-use")
            .add_tool_call(
                ToolCallEvent(kind=ToolCallKind.HTTP_API, method="GET", target="https://api.example.com/status")
            )
            .finish()
        )
        await store.save_trace(trace)
        row = await store.set_baseline("scenario-baseline", trace.trace_id)
        rows = await store.list_baselines(limit=10)
        loaded = await store.get_baseline("scenario-baseline")
        removed = await store.clear_baselines("scenario-baseline")
        await store.close()
        assert row["trace_id"] == trace.trace_id
        assert row["framework"] == "browser-use"
        assert len(rows) == 1
        assert loaded is not None
        assert loaded["trace_id"] == trace.trace_id
        assert removed == 1

    asyncio.run(run())


def test_trace_store_baseline_tracks_failed_checks(tmp_path: Path) -> None:
    async def run() -> None:
        store = TraceStore(db_path=tmp_path / "traces.db")
        await store.setup()
        trace = (
            TraceBuilder("scenario-checks-failed", "Scenario Checks Failed")
            .set_runtime_provenance(mode="adapter", framework="browser-use")
            .finish()
        )
        trace.evaluation = TraceEvaluation(
            passed=False,
            ase_score=0.5,
            total=1,
            passed_count=0,
            failed_count=1,
            failing_evaluators=["tool_called"],
        )
        await store.save_trace(trace)
        row = await store.set_baseline("scenario-checks-failed", trace.trace_id)
        await store.close()
        assert row["run_result"] == "failed"
        assert row["evaluation_status"] == "failed"

    asyncio.run(run())


def test_trace_store_migrates_existing_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy-traces.db"
    trace = (
        TraceBuilder("scenario-legacy", "Scenario Legacy")
        .set_runtime_provenance(mode="adapter", framework="browser-use")
        .add_tool_call(
            ToolCallEvent(kind=ToolCallKind.HTTP_API, method="GET", target="https://api.example.com/status")
        )
        .finish()
    )

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE traces (
                trace_id TEXT PRIMARY KEY,
                scenario_id TEXT NOT NULL,
                scenario_name TEXT NOT NULL,
                status TEXT NOT NULL,
                evaluation_status TEXT,
                ase_score REAL,
                runtime_mode TEXT,
                certification_level TEXT,
                started_at_ms REAL,
                trace_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO traces (
                trace_id, scenario_id, scenario_name, status, evaluation_status,
                ase_score, runtime_mode, certification_level, started_at_ms, trace_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace.trace_id,
                trace.scenario_id,
                trace.scenario_name,
                trace.status.value,
                None,
                None,
                "adapter",
                None,
                trace.started_at_ms,
                serialize(trace),
            ),
        )
        conn.commit()

    async def run() -> None:
        store = TraceStore(db_path=db_path)
        await store.setup()
        rows = await store.list_traces(scenario_id="scenario-legacy", limit=1)
        await store.close()
        assert len(rows) == 1
        assert rows[0]["runtime_mode"] == "adapter"
        assert rows[0]["framework"] == "browser-use"

    asyncio.run(run())

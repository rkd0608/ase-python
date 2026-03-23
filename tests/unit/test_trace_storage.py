from __future__ import annotations

import asyncio
from pathlib import Path

from ase.storage.trace_store import TraceStore
from ase.trace.builder import TraceBuilder
from ase.trace.model import ToolCallEvent, ToolCallKind
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
        assert stored is not None
        assert stored.trace_id == trace.trace_id

    asyncio.run(run())

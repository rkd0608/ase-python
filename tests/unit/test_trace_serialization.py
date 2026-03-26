from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from ase.trace.model import (
    LLMRequestEvent,
    LLMResponseEvent,
    ToolCallEvent,
    ToolCallKind,
    Trace,
    TraceEvent,
    TraceEventKind,
)


def _make_trace(events: list[TraceEvent] | None = None) -> Trace:
    return Trace(
        trace_id="trace-serialization",
        scenario_id="scenario-serialization",
        scenario_name="Trace Serialization",
        events=events or [],
    )


def _all_event_types_trace() -> Trace:
    # Map requested semantic event labels to the current TraceEvent model.
    return _make_trace(
        [
            TraceEvent(
                event_id="evt-tool-call",
                kind=TraceEventKind.TOOL_CALL,
                tool_call=ToolCallEvent(
                    kind=ToolCallKind.HTTP_API,
                    method="POST",
                    target="https://api.example.com/v1/tool",
                    payload={"query": "status"},
                    response_status=200,
                    response_body={"ok": True},
                    duration_ms=123.4,
                ),
                metadata={"semantic_type": "tool_call"},
            ),
            TraceEvent(
                event_id="evt-model-call",
                kind=TraceEventKind.LLM_REQUEST,
                llm_request=LLMRequestEvent(
                    model="gpt-test",
                    prompt_hash="abc123",
                    token_count_estimate=42,
                ),
                metadata={"semantic_type": "model_call"},
            ),
            TraceEvent(
                event_id="evt-output",
                kind=TraceEventKind.LLM_RESPONSE,
                llm_response=LLMResponseEvent(
                    model="gpt-test",
                    output_tokens=21,
                    finish_reason="stop",
                ),
                metadata={"semantic_type": "output"},
            ),
            TraceEvent(
                event_id="evt-error",
                kind=TraceEventKind.SCENARIO_END,
                metadata={"semantic_type": "error", "message": "synthetic error"},
            ),
            TraceEvent(
                event_id="evt-env-snapshot",
                kind=TraceEventKind.SCENARIO_START,
                metadata={"semantic_type": "env_snapshot", "env": {"python": "3.11"}},
            ),
        ]
    )


def test_trace_model_json_round_trip_with_all_event_types() -> None:
    trace = _all_event_types_trace()

    payload = trace.model_dump_json()
    restored = Trace.model_validate_json(payload)

    assert restored == trace


def test_trace_model_json_round_trip_empty_events() -> None:
    trace = _make_trace(events=[])

    payload = trace.model_dump_json()
    restored = Trace.model_validate_json(payload)

    assert restored == trace


def test_trace_model_json_round_trip_with_100_events() -> None:
    events = [
        TraceEvent(
            event_id=f"evt-{i}",
            kind=TraceEventKind.TOOL_CALL,
            tool_call=ToolCallEvent(
                kind=ToolCallKind.UNKNOWN,
                method="GET",
                target=f"resource-{i}",
                payload={"index": i},
            ),
        )
        for i in range(100)
    ]
    trace = _make_trace(events=events)

    payload = trace.model_dump_json()
    restored = Trace.model_validate_json(payload)

    assert restored == trace


def test_trace_model_json_round_trip_with_unicode_and_large_and_none_fields() -> None:
    large_payload = {f"k{i}": "🚀" * 64 for i in range(200)}
    trace = _make_trace(
        [
            TraceEvent(
                event_id="evt-unicode",
                kind=TraceEventKind.TOOL_CALL,
                parent_event_id=None,
                tool_call=ToolCallEvent(
                    kind=ToolCallKind.FILESYSTEM,
                    method="WRITE",
                    target="/tmp/данные/ファイル.txt",
                    payload={"text": "hello 🌍 — こんにちは — مرحبا"},
                    response_status=None,
                    response_body=None,
                    duration_ms=None,
                ),
                metadata={"note": "✨ unicode ✨"},
            ),
            TraceEvent(
                event_id="evt-large",
                kind=TraceEventKind.TOOL_RESPONSE,
                metadata={"blob": large_payload},
            ),
        ]
    )

    payload = trace.model_dump_json()
    restored = Trace.model_validate_json(payload)

    assert len(payload.encode("utf-8")) > 10 * 1024
    assert restored == trace


def test_trace_v1_payload_with_unknown_extra_fields_is_forward_compatible() -> None:
    payload: dict[str, Any] = _all_event_types_trace().model_dump(mode="json")
    payload["schema_version"] = 1
    payload["unknown_top_level"] = {"future": "field"}
    payload["events"][0]["unknown_event_field"] = "future-event-value"

    restored = Trace.model_validate(payload)

    assert restored.schema_version == 1
    assert restored.trace_id == payload["trace_id"]
    assert "unknown_top_level" not in restored.model_dump(mode="json")
    assert "unknown_event_field" not in restored.events[0].model_dump(mode="json")


def test_trace_json_validates_against_trace_schema() -> None:
    trace = _all_event_types_trace()
    trace_json = trace.model_dump_json()
    trace_dict = json.loads(trace_json)

    schema_path = Path("schemas/trace.v1.schema.json")
    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    else:
        schema = Trace.model_json_schema()

    jsonschema.validate(instance=trace_dict, schema=schema)

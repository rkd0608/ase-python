"""Instrumented example agent that emits ASE events directly."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

AGENT_ID = "instrumented-agent"
SESSION_ID = "sess-instrumented-example"
SPAN_ID = "instrumented-agent:search"
TARGET = "https://api.example.com/orders/ord-001"


def main() -> int:
    """Emit a stateful tool flow that exercises ASE's instrumented runtime path."""
    path = _event_path(_parse_args())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    _write(
        path,
        [
            _event("agent_start", agent_id=AGENT_ID, name=AGENT_ID),
            _event(
                "session_write",
                agent_id=AGENT_ID,
                session_id=SESSION_ID,
                data={"key": "intent", "value": "lookup"},
            ),
            _event(
                "tool_start",
                agent_id=AGENT_ID,
                span_id=SPAN_ID,
                tool_kind="http_api",
                method="GET",
                target=TARGET,
                name="lookup_order",
            ),
            _event(
                "tool_end",
                agent_id=AGENT_ID,
                span_id=SPAN_ID,
                tool_kind="http_api",
                method="GET",
                target=TARGET,
                status="passed",
                data={"status_code": 200},
            ),
            _event("agent_end", agent_id=AGENT_ID, status="passed"),
        ],
    )
    print("looked up ord-001")
    return 0


def _parse_args() -> argparse.Namespace:
    """Allow manual event destinations for example certification flows."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--events-out", type=Path, default=None)
    return parser.parse_args()


def _event_path(args: argparse.Namespace) -> Path:
    """Keep instrumented runs compatible with both CLI args and ASE env wiring."""
    if args.events_out is not None:
        return args.events_out
    env_path = os.environ.get("ASE_ADAPTER_EVENT_SOURCE")
    if env_path:
        return Path(env_path)
    return Path(__file__).with_name("events.generated.jsonl")


def _write(path: Path, events: list[dict[str, object]]) -> None:
    """Persist one deterministic event stream with no external imports."""
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")


def _event(event_type: str, **kwargs: object) -> dict[str, object]:
    """Build normalized events that the shared replay layer already understands."""
    return {
        "protocol_version": 1,
        "event_type": event_type,
        "event_id": f"{event_type}-{time.time_ns()}",
        "timestamp_ms": time.time() * 1000,
        "metadata": {
            "adapter_name": "instrumented-python",
            "framework": "custom-instrumented",
            "language": "python",
            "transport": "jsonl-stdio",
        },
        **kwargs,
    }


if __name__ == "__main__":
    raise SystemExit(main())

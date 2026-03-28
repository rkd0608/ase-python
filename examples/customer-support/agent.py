"""Deterministic customer-support example agent for ASE quickstarts."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

AGENT_ID = "customer-support-agent"
SPAN_ID = "customer-support-agent:refund"
TARGET = "https://api.example.com/refunds/ord-001"


def main() -> int:
    """Emit one safe refund flow so quickstarts exercise ASE deterministically."""
    event_path = _event_path(_parse_args())
    event_path.parent.mkdir(parents=True, exist_ok=True)
    event_path.unlink(missing_ok=True)
    _write_events(
        event_path,
        [
            _event("agent_start", agent_id=AGENT_ID, name=AGENT_ID),
            _event(
                "tool_start",
                agent_id=AGENT_ID,
                span_id=SPAN_ID,
                tool_kind="http_api",
                method="POST",
                target=TARGET,
                name="issue_refund",
                data={"order_id": "ord-001"},
            ),
            _event(
                "tool_end",
                agent_id=AGENT_ID,
                span_id=SPAN_ID,
                tool_kind="http_api",
                method="POST",
                target=TARGET,
                status="passed",
                data={"status_code": 200, "order_id": "ord-001"},
            ),
            _event("agent_end", agent_id=AGENT_ID, status="passed"),
        ],
    )
    print("refunded ord-001")
    return 0


def _parse_args() -> argparse.Namespace:
    """Allow explicit event output paths while still honoring ASE's env override."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--events-out", type=Path, default=None)
    return parser.parse_args()


def _event_path(args: argparse.Namespace) -> Path:
    """Prefer explicit CLI output, then ASE runtime output, then local default."""
    if args.events_out is not None:
        return args.events_out
    env_path = os.environ.get("ASE_ADAPTER_EVENT_SOURCE")
    if env_path:
        return Path(env_path)
    return Path(__file__).with_name("events.generated.jsonl")


def _write_events(path: Path, events: list[dict[str, object]]) -> None:
    """Persist events as JSONL without depending on the ASE package import path."""
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")


def _event(event_type: str, **kwargs: object) -> dict[str, object]:
    """Build adapter events with stable metadata for replay and certification."""
    return {
        "protocol_version": 1,
        "event_type": event_type,
        "event_id": f"{event_type}-{time.time_ns()}",
        "timestamp_ms": time.time() * 1000,
        "metadata": {
            "adapter_name": "customer-support-example",
            "framework": "custom",
            "language": "python",
            "transport": "jsonl-stdio",
        },
        **kwargs,
    }


if __name__ == "__main__":
    raise SystemExit(main())

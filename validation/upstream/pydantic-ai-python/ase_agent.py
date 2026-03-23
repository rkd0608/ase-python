"""Run a real upstream PydanticAI agent and emit ASE adapter events."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

ROOT = Path(__file__).resolve().parents[3]
UPSTREAM_ROOT = ROOT / ".upstream" / "pydantic-ai"
if str(UPSTREAM_ROOT) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_ROOT))

RunContext = __import__("pydantic_ai").RunContext

if TYPE_CHECKING:
    from pydantic_ai import Agent

    from ase.adapters.frameworks import PydanticAIAdapter

AGENT_ID = "pydantic-refund-agent"
SESSION_ID = "sess-pydantic-example"
SPAN_ID = "pydantic-refund-agent:issue_refund"
TARGET_URL = "https://api.example.com/refunds"


def _parse_args() -> argparse.Namespace:
    """Accept an optional event output path for certification runs."""
    default_path = Path(
        os.environ.get(
            "ASE_ADAPTER_EVENT_SOURCE",
            str(Path(__file__).with_name("events.generated.jsonl")),
        )
    )
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--events-out",
        type=Path,
        default=default_path,
    )
    return parser.parse_args()


def _build_agent(adapter: PydanticAIAdapter) -> Agent[None, object]:
    """Create a deterministic PydanticAI run that exercises one tool call."""
    from pydantic_ai import Agent

    agent = Agent("test")

    @agent.tool
    def issue_refund(ctx: RunContext[None]) -> str:
        del ctx
        adapter.tool_start(
            AGENT_ID,
            span_id=SPAN_ID,
            tool_kind="http_api",
            method="POST",
            target=TARGET_URL,
            name="issue_refund",
        )
        adapter.tool_end(
            AGENT_ID,
            span_id=SPAN_ID,
            tool_kind="http_api",
            method="POST",
            target=TARGET_URL,
            data={"status_code": 200},
        )
        return "refunded ord-001"

    return agent


def main() -> int:
    """Execute a real upstream PydanticAI tool run for ASE validation."""
    from ase.adapters.frameworks import PydanticAIAdapter
    from ase.adapters.io import JsonlFileEventSink

    args = _parse_args()
    args.events_out.unlink(missing_ok=True)
    adapter = PydanticAIAdapter(JsonlFileEventSink(args.events_out))
    agent = _build_agent(adapter)
    status = "passed"
    adapter.agent_start(AGENT_ID, name=AGENT_ID)
    adapter.session_write(AGENT_ID, SESSION_ID, key="intent", value="refund")
    try:
        result = agent.run_sync("refund ord-001")
        print(result.output)
        print(args.events_out)
        return 0
    except BaseException:
        status = "failed"
        raise
    finally:
        adapter.agent_end(AGENT_ID, status=status)


if __name__ == "__main__":
    raise SystemExit(main())

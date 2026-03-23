"""Run a real upstream OpenAI Agents flow and emit ASE adapter events."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

ROOT = Path(__file__).resolve().parents[3]
UPSTREAM_ROOT = ROOT / ".upstream" / "openai-agents-python"
if str(UPSTREAM_ROOT) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_ROOT))

if TYPE_CHECKING:
    from agents import Agent

    from ase.adapters.frameworks import OpenAIAgentsAdapter

AGENT_ID = "openai-refund-agent"
SESSION_ID = "sess-openai-example"
SPAN_ID = "openai-refund-agent:issue_refund"
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


def _build_agent(adapter: OpenAIAgentsAdapter) -> Agent:
    """Create a deterministic OpenAI Agents run around one tool call."""
    from agents import Agent, function_tool
    from tests.fake_model import FakeModel
    from tests.test_responses import (
        get_final_output_message,
        get_function_tool_call,
    )

    @function_tool
    def issue_refund(order_id: str) -> str:
        adapter.tool_start(
            AGENT_ID,
            span_id=SPAN_ID,
            tool_kind="http_api",
            method="POST",
            target=TARGET_URL,
            name="issue_refund",
            data={"order_id": order_id},
        )
        adapter.tool_end(
            AGENT_ID,
            span_id=SPAN_ID,
            tool_kind="http_api",
            method="POST",
            target=TARGET_URL,
            data={"status_code": 200, "order_id": order_id},
        )
        return f"refunded {order_id}"

    initial_output = [get_function_tool_call("issue_refund", '{"order_id":"ord-001"}')]
    model = FakeModel(initial_output=initial_output)
    model.set_next_output([get_final_output_message("refunded ord-001")])
    return Agent(name=AGENT_ID, model=model, tools=[issue_refund])


def main() -> int:
    """Execute a real upstream OpenAI Agents run for ASE validation."""
    from agents import Runner

    from ase.adapters.frameworks import OpenAIAgentsAdapter
    from ase.adapters.io import JsonlFileEventSink

    args = _parse_args()
    args.events_out.unlink(missing_ok=True)
    adapter = OpenAIAgentsAdapter(JsonlFileEventSink(args.events_out))
    agent = _build_agent(adapter)
    status = "passed"
    adapter.agent_start(AGENT_ID, name=AGENT_ID)
    adapter.session_write(AGENT_ID, SESSION_ID, key="intent", value="refund")
    try:
        result = Runner.run_sync(agent, input="refund ord-001")
        print(result.final_output)
        print(args.events_out)
        return 0
    except BaseException:
        status = "failed"
        raise
    finally:
        adapter.agent_end(AGENT_ID, status=status)


if __name__ == "__main__":
    raise SystemExit(main())

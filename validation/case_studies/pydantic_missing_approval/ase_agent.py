"""Run a real PydanticAI flow with an optional approval gate."""

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

AGENT_ID = "pydantic-approval-agent"
APPROVAL_ID = "refund-approval"
TARGET_URL = "https://api.example.com/refunds"


def _parse_args() -> argparse.Namespace:
    """Allow ASE to run the failing and fixed policy variants."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=["bad", "fixed"], default="fixed")
    parser.add_argument(
        "--events-out",
        type=Path,
        default=Path(
            os.environ.get(
                "ASE_ADAPTER_EVENT_SOURCE",
                str(Path(__file__).with_name("events.generated.jsonl")),
            )
        ),
    )
    return parser.parse_args()


def _build_agent(adapter: PydanticAIAdapter, variant: str) -> Agent[None, object]:
    """Keep the only behavior change at the approval boundary."""
    from pydantic_ai import Agent

    agent = Agent("test")

    @agent.tool
    def issue_refund(ctx: RunContext[None]) -> str:
        del ctx
        if variant == "fixed":
            adapter.approval(AGENT_ID, APPROVAL_ID, granted=True)
        adapter.tool_start(
            AGENT_ID,
            span_id=f"{AGENT_ID}:issue_refund",
            tool_kind="http_api",
            method="POST",
            target=TARGET_URL,
            name="issue_refund",
        )
        adapter.tool_end(
            AGENT_ID,
            span_id=f"{AGENT_ID}:issue_refund",
            tool_kind="http_api",
            method="POST",
            target=TARGET_URL,
            data={"status_code": 200, "order_id": "ord-001"},
        )
        return "refunded ord-001"

    return agent


def main() -> int:
    """Produce a real PydanticAI run with and without approval coverage."""
    from ase.adapters.frameworks import PydanticAIAdapter
    from ase.adapters.io import JsonlFileEventSink

    args = _parse_args()
    args.events_out.unlink(missing_ok=True)
    adapter = PydanticAIAdapter(JsonlFileEventSink(args.events_out))
    agent = _build_agent(adapter, args.variant)
    status = "passed"
    adapter.agent_start(AGENT_ID, name=AGENT_ID)
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

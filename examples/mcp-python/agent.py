"""Runnable MCP example backed by a real FastMCP server."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from ase.adapters.io import JsonlFileEventSink
from mcp.server.fastmcp import FastMCP

from ase.adapters.frameworks import MCPAdapter

AGENT_ID = "mcp-agent"
APPROVAL_ID = "mcp-write"
SESSION_ID = "sess-mcp-example"
SPAN_ID = "mcp-agent:resource-write"
TARGET = "mcp://filesystem/orders/ord-001"


def _parse_args() -> argparse.Namespace:
    """Accept an optional event output path for certification runs."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--events-out",
        type=Path,
        default=Path(__file__).with_name("events.generated.jsonl"),
    )
    return parser.parse_args()


def _build_server(adapter: MCPAdapter) -> FastMCP:
    """Create a real FastMCP server with one resource and one write tool."""
    server = FastMCP("ase-mcp")

    @server.resource("mcp://filesystem/orders/{order_id}")
    def order_resource(order_id: str) -> str:
        return f"order:{order_id}:pending"

    @server.tool(name="write_order")
    def write_order(order_id: str) -> str:
        target = f"mcp://filesystem/orders/{order_id}"
        adapter.resource_write(
            AGENT_ID,
            span_id=SPAN_ID,
            target=target,
            approval_id=APPROVAL_ID,
            session_id=SESSION_ID,
        )
        return f"wrote {target}"

    return server


async def main() -> int:
    """Execute a real MCP tool invocation and emit ASE adapter events."""
    args = _parse_args()
    args.events_out.unlink(missing_ok=True)
    adapter = MCPAdapter(JsonlFileEventSink(args.events_out))
    server = _build_server(adapter)
    adapter.agent_start(AGENT_ID, name=AGENT_ID)
    resource = await server.read_resource(TARGET)
    adapter.resource_read(
        AGENT_ID,
        session_id=SESSION_ID,
        target=TARGET,
        value=str(resource),
    )
    result = await server.call_tool("write_order", {"order_id": "ord-001"})
    adapter.agent_end(AGENT_ID, status="passed")
    print(result)
    print(args.events_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

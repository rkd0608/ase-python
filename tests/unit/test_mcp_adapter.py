"""Tests for MCP adapter event emission."""

from __future__ import annotations

from ase.adapters.frameworks.mcp import MCPAdapter
from ase.adapters.io import InMemoryEventSink


def test_mcp_adapter_emits_resource_read_and_write_flow() -> None:
    """MCP adapters should capture resource reads plus approval-gated writes."""
    sink = InMemoryEventSink()
    adapter = MCPAdapter(sink, version="1.0.0")

    adapter.resource_read(
        "agent-1",
        session_id="session-1",
        target="mcp://filesystem/orders/ord-001",
        value="order:ord-001:pending",
    )
    adapter.resource_write(
        "agent-1",
        span_id="span-1",
        target="mcp://filesystem/orders/ord-001",
        approval_id="approval-1",
        session_id="session-1",
    )

    event_types = [event.event_type.value for event in sink.events]
    assert event_types == ["session_read", "approval", "session_write", "tool_start", "tool_end"]
    assert sink.events[0].data["value"] == "order:ord-001:pending"
    assert sink.events[-1].protocol == "mcp"

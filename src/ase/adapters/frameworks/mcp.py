"""Official adapter SDK surface for MCP-backed runtimes."""

from __future__ import annotations

from ase.adapters.frameworks.base import FrameworkAdapterBase
from ase.adapters.io import AdapterEventSink


class MCPAdapter(FrameworkAdapterBase):
    """Emit ASE adapter events for MCP tools and resource access flows."""

    def __init__(
        self,
        sink: AdapterEventSink,
        *,
        version: str | None = None,
    ) -> None:
        super().__init__(
            sink,
            name="mcp-python",
            framework="mcp",
            language="python",
            version=version,
        )

    def resource_read(
        self,
        agent_id: str,
        *,
        session_id: str,
        target: str,
        value: object,
    ) -> None:
        """Emit MCP resource-read state without inflating tool-call metrics."""
        self.session_read(agent_id, session_id, key=target, value=value)

    def resource_write(
        self,
        agent_id: str,
        *,
        span_id: str,
        target: str,
        approval_id: str,
        session_id: str | None = None,
    ) -> None:
        """Emit an approval-backed MCP resource write tool flow."""
        self.approval(agent_id, approval_id, granted=True)
        if session_id is not None:
            self.session_write(agent_id, session_id, key="mcp_target", value=target)
        self.tool_start(
            agent_id,
            span_id=span_id,
            tool_kind="filesystem",
            method="WRITE",
            target=target,
            name="mcp_resource_write",
            protocol="mcp",
        )
        self.tool_end(
            agent_id,
            span_id=span_id,
            tool_kind="filesystem",
            method="WRITE",
            target=target,
            protocol="mcp",
            data={"status_code": 200, "resource": target},
            message="mcp write completed",
        )

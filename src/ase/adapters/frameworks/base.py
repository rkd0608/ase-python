"""Shared adapter SDK primitives for framework-specific integrations."""

from __future__ import annotations

from typing import Any, cast

import ulid

from ase.adapters.contract import AdapterContract
from ase.adapters.io import AdapterEventSink
from ase.adapters.model import AdapterEvent, AdapterEventType


class FrameworkAdapterBase(AdapterContract):
    """Common event-emission helpers shared across official adapters."""

    def __init__(
        self,
        sink: AdapterEventSink,
        *,
        name: str,
        framework: str,
        language: str,
        transport: str = "jsonl-stdio",
        version: str | None = None,
    ) -> None:
        self._sink = sink
        self._name = name
        self._framework = framework
        self._language = language
        self._transport = transport
        self._version = version

    @property
    def name(self) -> str:
        """Return the stable adapter name for certification output."""
        return self._name

    @property
    def transport(self) -> str:
        """Return the transport used for emitted adapter events."""
        return self._transport

    def emit(self, event: AdapterEvent) -> None:
        """Write a fully formed event to the configured sink."""
        self._sink.write(event)

    def enrich_policy_context(self, context: dict[str, object]) -> dict[str, object]:
        """Attach framework metadata used by policy evaluators and reporters."""
        return {
            **context,
            "adapter_name": self._name,
            "framework": self._framework,
            "language": self._language,
        }

    def inject_determinism(self, fixtures: dict[str, object]) -> dict[str, object]:
        """Expose fixtures unchanged as adapter runtime inputs by default."""
        return dict(fixtures)

    def agent_start(self, agent_id: str, name: str, **metadata: object) -> None:
        """Emit an agent_start event with framework metadata attached."""
        self.emit(
            self._event(
                AdapterEventType.AGENT_START,
                agent_id=agent_id,
                name=name,
                metadata=metadata,
            )
        )

    def agent_end(
        self,
        agent_id: str,
        *,
        status: str = "passed",
        message: str | None = None,
        **metadata: object,
    ) -> None:
        """Emit an agent_end event for the active framework run."""
        self.emit(
            self._event(
                AdapterEventType.AGENT_END,
                agent_id=agent_id,
                status=status,
                message=message,
                metadata=metadata,
            )
        )

    def tool_start(
        self,
        agent_id: str,
        *,
        span_id: str,
        tool_kind: str,
        method: str,
        target: str,
        name: str | None = None,
        protocol: str | None = None,
        data: dict[str, object] | None = None,
    ) -> None:
        """Emit a tool_start event for a framework tool call."""
        self.emit(
            self._event(
                AdapterEventType.TOOL_START,
                agent_id=agent_id,
                span_id=span_id,
                tool_kind=tool_kind,
                method=method,
                target=target,
                name=name,
                protocol=protocol,
                data=data,
            )
        )

    def tool_end(
        self,
        agent_id: str,
        *,
        span_id: str,
        tool_kind: str,
        method: str,
        target: str,
        status: str = "passed",
        protocol: str | None = None,
        data: dict[str, object] | None = None,
        message: str | None = None,
    ) -> None:
        """Emit a tool_end event for a framework tool call."""
        self.emit(
            self._event(
                AdapterEventType.TOOL_END,
                agent_id=agent_id,
                span_id=span_id,
                tool_kind=tool_kind,
                method=method,
                target=target,
                status=status,
                protocol=protocol,
                data=data,
                message=message,
            )
        )

    def session_write(
        self,
        agent_id: str,
        session_id: str,
        *,
        key: str,
        value: object,
    ) -> None:
        """Emit a session_write event for stateful frameworks."""
        self.emit(
            self._event(
                AdapterEventType.SESSION_WRITE,
                agent_id=agent_id,
                session_id=session_id,
                data={"key": key, "value": value},
            )
        )

    def session_read(
        self,
        agent_id: str,
        session_id: str,
        *,
        key: str,
        value: object,
    ) -> None:
        """Emit a session_read event for frameworks that expose state reads."""
        self.emit(
            self._event(
                AdapterEventType.SESSION_READ,
                agent_id=agent_id,
                session_id=session_id,
                data={"key": key, "value": value},
            )
        )

    def handoff(
        self,
        agent_id: str,
        target_agent_id: str,
        *,
        name: str,
        protocol: str = "adapter",
        data: dict[str, object] | None = None,
    ) -> None:
        """Emit a handoff event between two agents."""
        self.emit(
            self._event(
                AdapterEventType.HANDOFF,
                agent_id=agent_id,
                target_agent_id=target_agent_id,
                name=name,
                protocol=protocol,
                data=data,
            )
        )

    def approval(
        self,
        agent_id: str,
        approval_id: str,
        *,
        granted: bool = True,
    ) -> None:
        """Emit an approval event used by policy-aware flows."""
        self.emit(
            self._event(
                AdapterEventType.APPROVAL,
                agent_id=agent_id,
                approval_id=approval_id,
                granted=granted,
            )
        )

    def stream_chunk(
        self,
        agent_id: str,
        *,
        chunk_index: int,
        content: str,
        protocol: str = "stream",
    ) -> None:
        """Emit a streaming chunk event for realtime-style frameworks."""
        self.emit(
            self._event(
                AdapterEventType.STREAM_CHUNK,
                agent_id=agent_id,
                protocol=protocol,
                data={"chunk_index": chunk_index, "content": content},
            )
        )

    def _event(self, event_type: AdapterEventType, **kwargs: object) -> AdapterEvent:
        """Build a framework event with standard adapter metadata attached."""
        raw_metadata = kwargs.pop("metadata", None)
        metadata = cast(dict[str, Any], raw_metadata or {})
        if kwargs.get("data") is None:
            kwargs.pop("data", None)
        if kwargs.get("message") is None:
            kwargs.pop("message", None)
        metadata.setdefault("adapter_name", self._name)
        metadata.setdefault("framework", self._framework)
        metadata.setdefault("language", self._language)
        if self._version is not None:
            metadata.setdefault("adapter_version", self._version)
        metadata.setdefault("transport", self._transport)
        event_kwargs = cast(dict[str, Any], kwargs)
        return AdapterEvent(
            event_type=event_type,
            event_id=str(ulid.new()),
            metadata=metadata,
            **event_kwargs,
        )

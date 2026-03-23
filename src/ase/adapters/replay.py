"""Convert adapter event streams into ASE-native traces."""

from __future__ import annotations

from typing import Any

from ase.adapters.model import AdapterEvent, AdapterEventType
from ase.trace.builder import TraceBuilder
from ase.trace.model import (
    AdapterMetadata,
    AgentGraphNode,
    ExternalTraceRef,
    HandoffEdge,
    ProtocolEvent,
    RuntimeProvenance,
    SessionTraceEvent,
    ToolCallEvent,
    ToolCallKind,
    Trace,
    TraceStatus,
)


def trace_from_adapter_events(
    events: list[AdapterEvent],
    scenario_id: str,
    scenario_name: str,
) -> Trace:
    """Build an ASE trace from a validated adapter event stream."""
    builder = TraceBuilder(scenario_id=scenario_id, scenario_name=scenario_name)
    trace = _replay_events(builder, events)
    _attach_adapter_metadata(trace, events)
    return trace


def _replay_events(builder: TraceBuilder, events: list[AdapterEvent]) -> Trace:
    """Replay adapter events into trace-level tool calls and protocol blocks."""
    pending_tools: dict[str, AdapterEvent] = {}
    status = TraceStatus.PASSED
    error_message: str | None = None
    trace = builder.current_trace

    for event in events:
        _track_agent_node(trace, event)
        _attach_external_trace_ref(trace, event)
        if event.event_type == AdapterEventType.APPROVAL:
            builder.add_approval(approval=_approval_event(event))
            continue
        if event.event_type == AdapterEventType.TOOL_START:
            _append_tool_protocol_event(trace, event)
            pending_tools[event.span_id or event.event_id] = event
            continue
        if event.event_type == AdapterEventType.TOOL_END:
            _append_tool_call(builder, pending_tools, event)
            _append_tool_protocol_event(trace, event)
            if _is_error_status(event.status):
                status = TraceStatus.FAILED
                error_message = event.message or error_message
            continue
        if event.event_type in {
            AdapterEventType.SESSION_READ,
            AdapterEventType.SESSION_WRITE,
        }:
            trace.session_events.append(_session_event(event))
            trace.protocol_events.append(_protocol_event(event))
            continue
        if event.event_type == AdapterEventType.HANDOFF:
            trace.handoff_edges.append(_handoff_edge(event))
        if event.event_type in {
            AdapterEventType.HANDOFF,
            AdapterEventType.GUARDRAIL,
            AdapterEventType.HUMAN_FEEDBACK,
            AdapterEventType.STREAM_CHUNK,
        }:
            trace.protocol_events.append(_protocol_event(event))
        if event.event_type == AdapterEventType.AGENT_END and _is_error_status(event.status):
            status = TraceStatus.FAILED
            error_message = event.message or error_message

    if pending_tools and status == TraceStatus.PASSED:
        status = TraceStatus.ERROR
        error_message = "adapter event stream ended with unfinished tool spans"
    return builder.finish(status=status, error_message=error_message)


def _append_tool_call(
    builder: TraceBuilder,
    pending_tools: dict[str, AdapterEvent],
    event: AdapterEvent,
) -> None:
    """Combine tool_start/tool_end events into one ASE tool call record."""
    span_key = event.span_id or event.event_id
    start = pending_tools.pop(span_key, event)
    duration = max(event.timestamp_ms - start.timestamp_ms, 0.0)
    builder.add_tool_call(
        ToolCallEvent(
            kind=_tool_call_kind(event.tool_kind),
            method=event.method or "UNKNOWN",
            target=event.target or "unknown",
            payload=start.data or start.metadata,
            response_status=_response_status(event),
            response_body=_response_body(event),
            duration_ms=duration,
        )
    )


def _tool_call_kind(raw_kind: str | None) -> ToolCallKind:
    """Map adapter tool kinds onto ASE's native tool-call taxonomy."""
    try:
        return ToolCallKind(raw_kind or ToolCallKind.UNKNOWN.value)
    except ValueError:
        return ToolCallKind.UNKNOWN


def _track_agent_node(trace: Trace, event: AdapterEvent) -> None:
    """Register agent identities for multi-agent traces."""
    if not event.agent_id:
        return
    existing = {node.agent_id for node in trace.agent_graph.nodes}
    if event.agent_id in existing:
        return
    trace.agent_graph.nodes.append(
        AgentGraphNode(
            agent_id=event.agent_id,
            name=event.name,
            parent_agent_id=event.parent_agent_id,
            metadata=event.metadata,
        )
    )


def _attach_adapter_metadata(trace: Trace, events: list[AdapterEvent]) -> None:
    """Lift adapter metadata from the stream onto the trace root."""
    metadata = _first_metadata(events)
    adapter_name = str(metadata.get("adapter_name", "external-adapter"))
    transport = str(metadata.get("transport", "jsonl-stdio"))
    trace.adapter_metadata = AdapterMetadata(
        name=adapter_name,
        transport=transport,
        framework=_optional_str(metadata.get("framework")),
        language=_optional_str(metadata.get("language")),
        version=_optional_str(metadata.get("adapter_version")),
        source="adapter",
        metadata=dict(metadata),
    )
    trace.runtime_provenance = RuntimeProvenance(
        mode="adapter",
        framework=_optional_str(metadata.get("framework")),
        framework_version=_optional_str(metadata.get("framework_version")),
        adapter_name=adapter_name,
        adapter_version=_optional_str(metadata.get("adapter_version")),
        event_source=_optional_str(metadata.get("event_source")),
        metadata=dict(metadata),
    )


def _attach_external_trace_ref(trace: Trace, event: AdapterEvent) -> None:
    """Preserve references to external tracing systems when provided."""
    external = event.metadata.get("external_trace")
    if not isinstance(external, dict):
        return
    if not external.get("system") or not external.get("trace_id"):
        return
    trace.external_trace_refs.append(
        ExternalTraceRef(
            system=str(external["system"]),
            trace_id=str(external["trace_id"]),
            url=_optional_str(external.get("url")),
            metadata={
                key: value
                for key, value in external.items()
                if key not in {"system", "trace_id", "url"}
            },
        )
    )


def _session_event(event: AdapterEvent) -> SessionTraceEvent:
    """Translate adapter session activity into ASE session events."""
    return SessionTraceEvent(
        session_id=event.session_id or "unknown",
        operation=event.event_type.value,
        timestamp_ms=event.timestamp_ms,
        agent_id=event.agent_id,
        key=_optional_str(event.data.get("key")),
        metadata=dict(event.data),
    )


def _handoff_edge(event: AdapterEvent) -> HandoffEdge:
    """Translate adapter handoff events into ASE handoff edges."""
    return HandoffEdge(
        from_agent_id=event.agent_id or "unknown",
        to_agent_id=event.target_agent_id or "unknown",
        timestamp_ms=event.timestamp_ms,
        label=event.name,
        metadata=dict(event.data),
    )


def _protocol_event(event: AdapterEvent) -> ProtocolEvent:
    """Preserve non-tool protocol events for replay and certification."""
    return ProtocolEvent(
        protocol=event.protocol or "adapter",
        event_type=event.event_type.value,
        timestamp_ms=event.timestamp_ms,
        agent_id=event.agent_id,
        metadata={"data": dict(event.data), "message": event.message, **event.metadata},
    )


def _approval_event(event: AdapterEvent) -> Any:
    """Build an approval event compatible with TraceBuilder's API."""
    from ase.trace.model import ApprovalEvent

    return ApprovalEvent(
        approval_id=event.approval_id or "approval",
        actor=event.agent_id or "adapter",
        granted=bool(event.granted if event.granted is not None else True),
    )


def _response_status(event: AdapterEvent) -> int | None:
    """Extract a response status code from adapter data when present."""
    raw_status = event.data.get("response_status") or event.data.get("status_code")
    return raw_status if isinstance(raw_status, int) else None


def _response_body(event: AdapterEvent) -> dict[str, Any] | None:
    """Preserve tool-end payloads and protocol hints for imported traces."""
    body = dict(event.data or {})
    if event.protocol is not None:
        body.setdefault("protocol", event.protocol)
    return body or None


def _append_tool_protocol_event(trace: Trace, event: AdapterEvent) -> None:
    """Preserve non-default tool protocols such as MCP alongside tool calls."""
    if event.protocol is not None:
        trace.protocol_events.append(_protocol_event(event))


def _is_error_status(status: str | None) -> bool:
    """Treat explicit error-like statuses as failed execution outcomes."""
    return (status or "").lower() in {"error", "failed", "failure", "timeout"}


def _first_metadata(events: list[AdapterEvent]) -> dict[str, Any]:
    """Return the first non-empty metadata mapping from the stream."""
    for event in events:
        if event.metadata:
            return dict(event.metadata)
    return {}


def _optional_str(value: Any) -> str | None:
    """Convert optional values to strings when present."""
    if value is None:
        return None
    return str(value)

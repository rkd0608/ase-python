"""Adapter protocol models for ingesting external agent runtimes into ASE."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

ADAPTER_PROTOCOL_VERSION = 1


class AdapterTransport(StrEnum):
    """Describe how an external runtime sends adapter events to ASE."""

    JSONL_STDIO = "jsonl-stdio"
    HTTP = "http"


class AdapterEventType(StrEnum):
    """Enumerate normalized lifecycle and protocol events for adapters."""

    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    HANDOFF = "handoff"
    GUARDRAIL = "guardrail"
    APPROVAL = "approval"
    SESSION_READ = "session_read"
    SESSION_WRITE = "session_write"
    HUMAN_FEEDBACK = "human_feedback"
    STREAM_CHUNK = "stream_chunk"


class AdapterEvent(BaseModel):
    """Represent one normalized adapter event emitted by a framework runtime."""

    protocol_version: int = ADAPTER_PROTOCOL_VERSION
    event_type: AdapterEventType
    timestamp_ms: float = Field(default_factory=lambda: time.time() * 1000)
    event_id: str
    span_id: str | None = None
    run_id: str | None = None
    agent_id: str | None = None
    parent_agent_id: str | None = None
    target_agent_id: str | None = None
    name: str | None = None
    tool_kind: str | None = None
    method: str | None = None
    target: str | None = None
    session_id: str | None = None
    approval_id: str | None = None
    granted: bool | None = None
    status: str | None = None
    protocol: str | None = None
    message: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_required_fields(self) -> AdapterEvent:
        """Enforce event-specific fields so replay remains deterministic."""
        if (
            self.event_type in {AdapterEventType.TOOL_START, AdapterEventType.TOOL_END}
            and (not self.tool_kind or not self.method or not self.target)
        ):
            raise ValueError("tool_start/tool_end require tool_kind, method, and target")
        if self.event_type == AdapterEventType.APPROVAL and not self.approval_id:
            raise ValueError("approval requires approval_id")
        if self.event_type in {
            AdapterEventType.SESSION_READ,
            AdapterEventType.SESSION_WRITE,
        } and not self.session_id:
            raise ValueError("session_read/session_write require session_id")
        if self.event_type == AdapterEventType.HANDOFF and not self.target_agent_id:
            raise ValueError("handoff requires target_agent_id")
        return self


class AdapterVerificationResult(BaseModel):
    """Capture pass/fail validation results for an adapter event stream."""

    passed: bool
    total_events: int
    event_type_counts: dict[str, int] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

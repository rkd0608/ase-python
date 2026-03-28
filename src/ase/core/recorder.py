"""Trace recorder used by the engine and runtime helpers.

Recorder keeps the engine logic small by translating runtime actions onto the
append-only trace builder in one place.
"""

from __future__ import annotations

from typing import Any

from ase.trace.builder import TraceBuilder, fixture_hash
from ase.trace.model import ApprovalEvent, ToolCallEvent, ToolCallKind, Trace, TraceStatus


class Recorder:
    """Collect runtime events and finish one trace with consistent metadata."""

    def __init__(
        self,
        *,
        scenario_id: str,
        scenario_name: str,
        tags: dict[str, str] | None = None,
    ) -> None:
        self._builder = TraceBuilder(scenario_id, scenario_name, tags=tags)

    @property
    def trace_id(self) -> str:
        """Expose the trace identifier so subprocesses can correlate output."""
        return self._builder.current_trace.trace_id

    def set_runtime_provenance(self, **kwargs: object) -> None:
        """Persist runtime methodology once at the start of a run."""
        self._builder.set_runtime_provenance(
            mode=str(kwargs.get("mode", "unknown")),
            framework=_optional_str(kwargs.get("framework")),
            framework_version=_optional_str(kwargs.get("framework_version")),
            adapter_name=_optional_str(kwargs.get("adapter_name")),
            adapter_version=_optional_str(kwargs.get("adapter_version")),
            conformance_bundle_version=_optional_str(
                kwargs.get("conformance_bundle_version")
            ),
            event_source=_optional_str(kwargs.get("event_source")),
            metadata=_metadata(kwargs.get("metadata")),
        )

    def record_approval(self, *, approval_id: str, actor: str, granted: bool) -> None:
        """Preserve seeded approvals so policy evaluators can replay them later."""
        self._builder.add_approval(
            ApprovalEvent(approval_id=approval_id, actor=actor, granted=granted)
        )

    def set_determinism_metadata(
        self,
        *,
        fixture_payload: dict[str, Any],
        replay_key: str,
        baseline_trace_id: str | None = None,
    ) -> None:
        """Attach deterministic fixture metadata used by compare and replay flows."""
        self._builder.set_determinism(
            fixture_hash=fixture_hash(fixture_payload),
            replay_key=replay_key,
            baseline_trace_id=baseline_trace_id,
        )

    def record_tool_call(
        self,
        *,
        kind: ToolCallKind,
        method: str,
        target: str,
        payload: dict[str, Any] | None = None,
        response_status: int | None = None,
        response_body: dict[str, Any] | None = None,
        duration_ms: float | None = None,
    ) -> None:
        """Convert one observed tool interaction into a trace event."""
        self._builder.add_tool_call(
            ToolCallEvent(
                kind=kind,
                method=method,
                target=target,
                payload=dict(payload or {}),
                response_status=response_status,
                response_body=response_body,
                duration_ms=duration_ms,
            )
        )

    def finish(
        self,
        *,
        status: TraceStatus,
        error_message: str | None = None,
        stderr_output: str | None = None,
    ) -> Trace:
        """Finalize one trace and preserve stderr alongside the trace root."""
        trace = self._builder.finish(status=status, error_message=error_message)
        trace.stderr_output = stderr_output
        return trace


def _optional_str(value: object) -> str | None:
    """Normalize optional provenance fields into the builder's expected types."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _metadata(value: object) -> dict[str, object] | None:
    """Preserve runtime metadata when callers pass one dictionary-like payload."""
    if isinstance(value, dict):
        return dict(value)
    return None

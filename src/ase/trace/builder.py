"""Helpers for incrementally constructing ASE traces."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import ulid

from ase.errors import TraceError
from ase.trace.model import (
    ApprovalEvent,
    DeterminismMetadata,
    LLMRequestEvent,
    LLMResponseEvent,
    RuntimeProvenance,
    ToolCallEvent,
    Trace,
    TraceEvent,
    TraceEventKind,
    TraceMetrics,
    TraceStatus,
)


class TraceBuilder:
    """Build one append-only trace from runtime events."""

    def __init__(
        self,
        scenario_id: str,
        scenario_name: str,
        tags: dict[str, str] | None = None,
    ) -> None:
        self._trace = Trace(
            trace_id=str(ulid.new()),
            scenario_id=scenario_id,
            scenario_name=scenario_name,
            tags=dict(tags or {}),
        )

    @property
    def current_trace(self) -> Trace:
        """Expose the in-progress trace for replay helpers."""
        return self._trace

    def add_tool_call(self, tool_call: ToolCallEvent) -> TraceBuilder:
        """Append one tool-call event to the trace."""
        self._trace.events.append(
            TraceEvent(
                event_id=str(ulid.new()),
                kind=TraceEventKind.TOOL_CALL,
                tool_call=tool_call,
            )
        )
        return self

    def add_approval(self, approval: ApprovalEvent) -> TraceBuilder:
        """Append one approval event to the trace."""
        self._trace.events.append(
            TraceEvent(
                event_id=str(ulid.new()),
                kind=TraceEventKind.APPROVAL,
                approval=approval,
            )
        )
        return self

    def add_llm_request(self, llm_request: LLMRequestEvent) -> TraceBuilder:
        """Append one LLM request event to the trace."""
        self._trace.events.append(
            TraceEvent(
                event_id=str(ulid.new()),
                kind=TraceEventKind.LLM_REQUEST,
                llm_request=llm_request,
            )
        )
        return self

    def add_llm_response(self, llm_response: LLMResponseEvent) -> TraceBuilder:
        """Append one LLM response event to the trace."""
        self._trace.events.append(
            TraceEvent(
                event_id=str(ulid.new()),
                kind=TraceEventKind.LLM_RESPONSE,
                llm_response=llm_response,
            )
        )
        return self

    def add_raw_event(self, event: TraceEvent) -> TraceBuilder:
        """Append one fully formed trace event."""
        self._trace.events.append(event)
        return self

    def set_runtime_provenance(
        self,
        mode: str,
        framework: str | None = None,
        framework_version: str | None = None,
        adapter_name: str | None = None,
        adapter_version: str | None = None,
        conformance_bundle_version: str | None = None,
        event_source: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> TraceBuilder:
        """Persist runtime provenance on the trace root."""
        self._trace.runtime_provenance = RuntimeProvenance(
            mode=mode,
            framework=framework,
            framework_version=framework_version,
            adapter_name=adapter_name,
            adapter_version=adapter_version,
            conformance_bundle_version=conformance_bundle_version,
            event_source=event_source,
            metadata=dict(metadata or {}),
        )
        return self

    def set_determinism(
        self,
        fixture_hash: str | None = None,
        replay_key: str | None = None,
        baseline_trace_id: str | None = None,
    ) -> TraceBuilder:
        """Persist deterministic replay metadata on the trace root."""
        self._trace.determinism = DeterminismMetadata(
            fixture_hash=fixture_hash,
            replay_key=replay_key,
            baseline_trace_id=baseline_trace_id,
        )
        return self

    def finish(
        self,
        status: TraceStatus = TraceStatus.PASSED,
        error_message: str | None = None,
    ) -> Trace:
        """Finalize the trace and compute aggregate metrics."""
        if self._trace.status != TraceStatus.RUNNING and self._trace.ended_at_ms is not None:
            raise TraceError(f"trace already finished: {self._trace.trace_id}")
        self._trace.status = status
        self._trace.ended_at_ms = time.time() * 1000
        self._trace.error_message = error_message
        self._trace.metrics = _compute_metrics(self._trace)
        return self._trace


def _compute_metrics(trace: Trace) -> TraceMetrics:
    """Compute aggregate metrics from the trace event stream."""
    metrics = TraceMetrics()
    metrics.total_duration_ms = max(
        (trace.ended_at_ms or trace.started_at_ms) - trace.started_at_ms,
        0.0,
    )
    for event in trace.events:
        if event.kind == TraceEventKind.TOOL_CALL and event.tool_call is not None:
            metrics.total_tool_calls += 1
            key = event.tool_call.kind.value
            metrics.tool_call_breakdown[key] = metrics.tool_call_breakdown.get(key, 0) + 1
        if event.kind == TraceEventKind.LLM_REQUEST:
            metrics.total_llm_calls += 1
            if event.llm_request and event.llm_request.token_count_estimate:
                metrics.total_tokens_used += event.llm_request.token_count_estimate
        if event.kind == TraceEventKind.LLM_RESPONSE and event.llm_response is not None:
            metrics.total_tokens_used += event.llm_response.output_tokens
    return metrics


def fixture_hash(payload: dict[str, Any]) -> str:
    """Compute a stable content hash for deterministic fixture payloads."""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

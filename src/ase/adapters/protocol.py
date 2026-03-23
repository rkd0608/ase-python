"""Read and verify adapter JSONL event streams."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ase.adapters.model import AdapterEvent, AdapterEventType, AdapterVerificationResult
from ase.errors import AdapterProtocolError


def read_jsonl_events(path: Path) -> list[AdapterEvent]:
    """Load a JSONL adapter event file with contextual parse errors."""
    if not path.exists():
        raise AdapterProtocolError(f"adapter event file not found: {path}")
    events: list[AdapterEvent] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AdapterProtocolError(f"failed to read adapter event file {path}: {exc}") from exc
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            events.append(AdapterEvent.model_validate(payload))
        except Exception as exc:
            raise AdapterProtocolError(
                f"invalid adapter event at {path}:{index}: {exc}"
            ) from exc
    return events


def verify_events(events: list[AdapterEvent]) -> AdapterVerificationResult:
    """Validate event ordering and structural invariants for replay safety."""
    errors: list[str] = []
    warnings: list[str] = []
    counts = Counter(event.event_type.value for event in events)
    if not events:
        errors.append("adapter event stream is empty")
    if counts[AdapterEventType.AGENT_START.value] == 0:
        errors.append("missing agent_start event")
    if counts[AdapterEventType.AGENT_END.value] == 0:
        errors.append("missing agent_end event")

    open_spans: set[str] = set()
    for event in events:
        if event.event_type == AdapterEventType.TOOL_START:
            open_spans.add(event.span_id or event.event_id)
        if event.event_type == AdapterEventType.TOOL_END:
            span_id = event.span_id or event.event_id
            if span_id not in open_spans:
                errors.append(f"tool_end missing matching tool_start for span {span_id}")
            else:
                open_spans.remove(span_id)
    if open_spans:
        warnings.append("adapter event stream ended with open tool spans")

    return AdapterVerificationResult(
        passed=not errors,
        total_events=len(events),
        event_type_counts=dict(counts),
        errors=errors,
        warnings=warnings,
    )


def read_and_verify(path: Path) -> tuple[list[AdapterEvent], AdapterVerificationResult]:
    """Load one adapter event file and return both events and verification."""
    events = read_jsonl_events(path)
    return events, verify_events(events)

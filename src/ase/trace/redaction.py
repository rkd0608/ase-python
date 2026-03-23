"""No-op redaction helpers for persisted traces."""

from __future__ import annotations

from ase.trace.model import Trace


def redact_trace(trace: Trace) -> Trace:
    """Return the trace unchanged until a richer redaction layer is restored."""
    return trace

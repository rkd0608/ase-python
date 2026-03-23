"""Event sinks for official ASE adapter SDKs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from ase.adapters.model import AdapterEvent
from ase.errors import AdapterError


class AdapterEventSink(Protocol):
    """Define the minimal write surface required by adapter SDKs."""

    def write(self, event: AdapterEvent) -> None:
        """Persist one adapter event."""


class JsonlFileEventSink:
    """Append adapter events to disk for replay and certification."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, event: AdapterEvent) -> None:
        """Write one JSONL adapter event with contextual file errors."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.model_dump(), separators=(",", ":")))
                handle.write("\n")
        except OSError as exc:
            raise AdapterError(f"failed to write adapter event sink {self._path}: {exc}") from exc


class InMemoryEventSink:
    """Retain adapter events in memory for tests and local examples."""

    def __init__(self) -> None:
        self._events: list[AdapterEvent] = []

    def write(self, event: AdapterEvent) -> None:
        """Append one event to the in-memory sink."""
        self._events.append(event)

    @property
    def events(self) -> list[AdapterEvent]:
        """Return a snapshot of all emitted events."""
        return list(self._events)

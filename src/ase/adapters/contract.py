"""Adapter contract shared by official ASE framework integrations."""

from __future__ import annotations

from typing import Protocol

from ase.adapters.model import AdapterEvent


class AdapterContract(Protocol):
    """Define the stable surface ASE adapters expose to frameworks and tests."""

    @property
    def name(self) -> str:
        """Return the stable adapter identifier used in traces and reports."""

    @property
    def transport(self) -> str:
        """Return the transport used to emit adapter events."""

    def emit(self, event: AdapterEvent) -> None:
        """Persist one normalized ASE adapter event."""

    def enrich_policy_context(self, context: dict[str, object]) -> dict[str, object]:
        """Attach adapter metadata used by evaluators and reporters."""

    def inject_determinism(self, fixtures: dict[str, object]) -> dict[str, object]:
        """Expose deterministic fixtures to the framework runtime."""

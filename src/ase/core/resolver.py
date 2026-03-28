"""Resolver for routing tool kinds onto active environments."""

from __future__ import annotations

from typing import Any

from ase.trace.model import ToolCallKind


class Resolver:
    """Map normalized tool-call kinds onto prepared environment providers."""

    def __init__(self) -> None:
        self._providers: dict[ToolCallKind, Any] = {}

    def register(self, kind: ToolCallKind, provider: Any) -> None:
        """Bind one tool kind to the provider that should service it."""
        self._providers[kind] = provider

    def resolve(self, kind: ToolCallKind) -> Any | None:
        """Look up the provider for one normalized tool kind."""
        return self._providers.get(kind)

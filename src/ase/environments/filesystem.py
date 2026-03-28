"""Filesystem fixture environment for deterministic local state."""

from __future__ import annotations

from typing import Any

from ase.environments.base import EnvironmentProvider
from ase.errors import ASEError
from ase.scenario.model import FilesystemEntryFixture


class FilesystemEnvironment(EnvironmentProvider):
    """Simulate a writable file tree without touching the developer filesystem."""

    def __init__(self, entries: list[FilesystemEntryFixture]) -> None:
        self._entries = list(entries)
        self._files: dict[str, dict[str, Any]] = {}

    async def setup(self) -> None:
        """Load deterministic fixture entries into one in-memory file map."""
        self._files = {
            entry.path: {"content": entry.content, "writable": entry.writable}
            for entry in self._entries
        }

    async def teardown(self) -> None:
        """Clear in-memory file state between runs."""
        self._files.clear()

    async def read(self, path: str) -> str:
        """Expose stable reads for agents and replay helpers."""
        try:
            return str(self._files[path]["content"])
        except KeyError as exc:
            raise ASEError(f"filesystem path not found: {path}") from exc

    async def write(self, path: str, content: str) -> None:
        """Allow writes only when the fixture declared that path mutable."""
        entry = self._files.get(path)
        if entry is not None and not bool(entry.get("writable")):
            raise ASEError(f"filesystem path is read-only: {path}")
        self._files[path] = {"content": content, "writable": True}

    async def snapshot(self) -> dict[str, dict[str, Any]]:
        """Return current file state for post-run assertions and debugging."""
        return {path: dict(entry) for path, entry in self._files.items()}

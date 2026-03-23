"""OpenAI Agents adapter helpers for ASE's neutral event protocol."""

from __future__ import annotations

from ase.adapters.frameworks.base import FrameworkAdapterBase
from ase.adapters.io import AdapterEventSink


class OpenAIAgentsAdapter(FrameworkAdapterBase):
    """Bind the generic adapter protocol to OpenAI Agents metadata."""

    def __init__(self, sink: AdapterEventSink, *, version: str | None = None) -> None:
        super().__init__(
            sink,
            name="openai-agents-python",
            framework="openai-agents",
            language="python",
            version=version,
        )

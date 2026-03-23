"""PydanticAI adapter helpers for ASE's neutral event protocol."""

from __future__ import annotations

from ase.adapters.frameworks.base import FrameworkAdapterBase
from ase.adapters.io import AdapterEventSink


class PydanticAIAdapter(FrameworkAdapterBase):
    """Bind the generic adapter protocol to PydanticAI metadata."""

    def __init__(self, sink: AdapterEventSink, *, version: str | None = None) -> None:
        super().__init__(
            sink,
            name="pydantic-ai-python",
            framework="pydantic-ai",
            language="python",
            version=version,
        )

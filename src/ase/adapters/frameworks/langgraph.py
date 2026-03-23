"""LangGraph adapter helpers for ASE's neutral event protocol."""

from __future__ import annotations

from ase.adapters.frameworks.base import FrameworkAdapterBase
from ase.adapters.io import AdapterEventSink


class LangGraphAdapter(FrameworkAdapterBase):
    """Bind the generic adapter protocol to LangGraph metadata."""

    def __init__(self, sink: AdapterEventSink, *, version: str | None = None) -> None:
        super().__init__(
            sink,
            name="langgraph-python",
            framework="langgraph",
            language="python",
            version=version,
        )

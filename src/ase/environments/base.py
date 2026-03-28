"""Base contract for scenario environments.

ASE environments isolate mutable backends behind one small async interface so
the engine can set up and tear down simulations without knowing backend
details.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class EnvironmentProvider(ABC):
    """Describe why simulated backends need one shared lifecycle contract."""

    @abstractmethod
    async def setup(self) -> None:
        """Prepare deterministic state before the scenario starts."""

    @abstractmethod
    async def teardown(self) -> None:
        """Release any resources held by the environment after the run."""

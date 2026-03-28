"""HTTP API replay environment for deterministic tests."""

from __future__ import annotations

from typing import Any

from ase.environments.base import EnvironmentProvider
from ase.errors import ASEError
from ase.scenario.model import APISeed


class APIEnvironment(EnvironmentProvider):
    """Replay seeded HTTP interactions without touching live services."""

    def __init__(self, seed: APISeed | None = None) -> None:
        self._seed = seed or APISeed()
        self.access_log: list[dict[str, Any]] = []
        self._responses: dict[tuple[str, str], dict[str, Any]] = {}

    async def setup(self) -> None:
        """Index recorded interactions so proxy or direct runtimes can replay them."""
        for item in self._seed.recordings:
            request = dict(item.get("request", {}))
            response = dict(item.get("response", {}))
            method = str(request.get("method", "GET")).upper()
            target = str(request.get("url", request.get("target", "")))
            self._responses[(method, target)] = response

    async def teardown(self) -> None:
        """Discard captured access history between runs."""
        self.access_log.clear()
        self._responses.clear()

    async def request(
        self,
        method: str,
        target: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resolve one API request against seeded recordings with clear misses."""
        normalized_method = method.upper()
        self.access_log.append(
            {"method": normalized_method, "target": target, "payload": dict(payload or {})}
        )
        try:
            return dict(self._responses[(normalized_method, target)])
        except KeyError as exc:
            raise ASEError(
                f"no api replay fixture for {normalized_method} {target}"
            ) from exc

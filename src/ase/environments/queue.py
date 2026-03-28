"""Queue and webhook fixture environment for event-driven scenarios."""

from __future__ import annotations

from typing import Any

from ase.environments.base import EnvironmentProvider
from ase.scenario.model import QueueMessageFixture, WebhookEventFixture


class QueueEnvironment(EnvironmentProvider):
    """Replay queue and webhook inputs without depending on external brokers."""

    def __init__(
        self,
        *,
        queue_messages: list[QueueMessageFixture],
        webhook_events: list[WebhookEventFixture],
    ) -> None:
        self._seed_messages = list(queue_messages)
        self._seed_webhooks = list(webhook_events)
        self.messages: list[dict[str, Any]] = []
        self.webhooks: list[dict[str, Any]] = []

    async def setup(self) -> None:
        """Load queued inputs into in-memory buffers for deterministic access."""
        self.messages = [item.model_dump() for item in self._seed_messages]
        self.webhooks = [item.model_dump() for item in self._seed_webhooks]

    async def teardown(self) -> None:
        """Discard queued state after each run."""
        self.messages.clear()
        self.webhooks.clear()

    async def publish(self, queue: str, body: dict[str, Any]) -> dict[str, Any]:
        """Capture new queue messages instead of sending them to a broker."""
        message = {"queue": queue, "body": dict(body)}
        self.messages.append(message)
        return message

    async def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        """Expose queue state for policy or debugging flows."""
        return {"messages": list(self.messages), "webhooks": list(self.webhooks)}

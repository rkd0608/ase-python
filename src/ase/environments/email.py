"""Email capture environment for simulated agent actions."""

from __future__ import annotations

from typing import Any

from ase.environments.base import EnvironmentProvider


class EmailEnvironment(EnvironmentProvider):
    """Capture outbound email actions so scenarios can assert on side effects."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def setup(self) -> None:
        """Reset captured messages at the start of a run."""
        self.messages.clear()

    async def teardown(self) -> None:
        """Drop captured messages so runs stay isolated."""
        self.messages.clear()

    async def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist one email payload instead of delivering it externally."""
        message = {
            "to": to,
            "subject": subject,
            "body": body,
            "metadata": dict(metadata or {}),
        }
        self.messages.append(message)
        return {"ok": True, "message_id": f"email-{len(self.messages)}"}

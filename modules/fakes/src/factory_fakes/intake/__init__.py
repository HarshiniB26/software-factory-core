"""Chat-shaped intake that keeps threads in memory."""

from typing import Any
from uuid import UUID

from factory_contracts import ContractError, FollowUpKind, RequestDraft


class FakeIntake:
    def __init__(self) -> None:
        self._threads: dict[str, dict[str, str]] = {}
        self.acks: list[tuple[str, UUID]] = []

    async def open_thread(self, user: str, target: str) -> str:
        thread_id = f"thread-{len(self._threads) + 1}"
        self._threads[thread_id] = {"user": user, "target": target}
        return thread_id

    async def receive(self, message: str, attachments: list[Any]) -> RequestDraft:
        title = message.splitlines()[0][:80] if message else "request"
        return RequestDraft(title=title, body=message, requester="local", kind="new")

    async def follow_up(self, thread_id: str, message: str) -> RequestDraft:
        if thread_id not in self._threads:
            raise ContractError(f"unknown thread {thread_id}")
        kind: FollowUpKind = "child" if message.lower().startswith("also") else "revise"
        return RequestDraft(
            title=message[:80],
            body=message,
            requester="local",
            kind=kind,
            thread_id=thread_id,
        )

    async def ack(self, thread_id: str, request_id: UUID) -> None:
        if thread_id not in self._threads:
            raise ContractError(f"unknown thread {thread_id}")
        self.acks.append((thread_id, request_id))

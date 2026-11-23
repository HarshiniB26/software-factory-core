"""Turn a GitHub issue labeled factory into a request draft. Other issues are ignored."""

import json
from typing import Any
from uuid import UUID

from factory_contracts import ContractError, RequestDraft


class GitHubIssueIntake:
    def __init__(self) -> None:
        self._threads: dict[str, dict[str, str]] = {}

    async def open_thread(self, user: str, target: str) -> str:
        thread_id = f"issue-{len(self._threads) + 1}"
        self._threads[thread_id] = {"user": user, "target": target}
        return thread_id

    async def receive(self, message: str, attachments: list[Any]) -> RequestDraft:
        event = _parse(message)
        labels = [str(label) for label in event.get("labels", [])]
        if "factory" not in labels and event:
            raise ContractError("issue is not labeled factory")
        title = str(event.get("title") or message.splitlines()[0][:80])
        body = str(event.get("body") or message)
        return RequestDraft(
            title=title, body=body, requester=str(event.get("user") or "github"), kind="new"
        )

    async def follow_up(self, thread_id: str, message: str) -> RequestDraft:
        if thread_id not in self._threads:
            raise ContractError(f"unknown thread {thread_id}")
        kind = "child" if message.lower().startswith("also") else "revise"
        return RequestDraft(
            title=message[:80], body=message, requester="github", kind=kind, thread_id=thread_id
        )

    async def ack(self, thread_id: str, request_id: UUID) -> None:
        if thread_id not in self._threads:
            raise ContractError(f"unknown thread {thread_id}")


def _parse(message: str) -> dict[str, Any]:
    try:
        data = json.loads(message)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}

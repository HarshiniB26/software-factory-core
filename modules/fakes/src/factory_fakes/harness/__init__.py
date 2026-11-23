"""Harness that records a task and streams a finite event list."""

from collections.abc import AsyncIterator
from typing import Literal
from uuid import uuid4

from factory_contracts import (
    ContractError,
    HarnessCapabilities,
    HarnessEvent,
    HarnessResult,
    TaskSpec,
    Usage,
)


class _Task:
    def __init__(self, spec: TaskSpec) -> None:
        self.spec = spec
        self.messages: list[str] = []
        self.status: Literal["ok", "failed", "cancelled"] = "ok"


class FakeHarnessAdapter:
    def __init__(self) -> None:
        self._tasks: dict[str, _Task] = {}

    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities(streaming=True, worktrees=False, name="fake")

    async def start_task(self, task: TaskSpec) -> str:
        task_id = f"task-{uuid4().hex[:8]}"
        self._tasks[task_id] = _Task(task)
        return task_id

    async def stream_events(self, task_id: str) -> AsyncIterator[HarnessEvent]:
        task = self._require(task_id)
        yield HarnessEvent(type="started", message=task.spec.instruction)
        for message in task.messages:
            yield HarnessEvent(type="message", message=message)

    async def send_message(self, task_id: str, message: str) -> None:
        self._require(task_id).messages.append(message)

    async def get_result(self, task_id: str) -> HarnessResult:
        task = self._require(task_id)
        summary = task.spec.instruction if task.status == "ok" else "cancelled"
        return HarnessResult(status=task.status, summary=summary)

    async def cancel(self, task_id: str) -> None:
        self._require(task_id).status = "cancelled"

    async def usage(self, task_id: str) -> Usage:
        self._require(task_id)
        return Usage(tokens=1)

    def _require(self, task_id: str) -> _Task:
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise ContractError(f"unknown task {task_id}") from exc

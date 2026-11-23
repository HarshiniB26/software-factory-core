"""Fixture harness that still honors the HarnessAdapter contract."""

from collections.abc import AsyncGenerator
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
        self.summary = spec.instruction
        self.usage = Usage(tokens=1)


class FixtureHarness:
    name = "fixture"
    vendor = "fixture"

    def __init__(self) -> None:
        self._tasks: dict[str, _Task] = {}

    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities(streaming=True, worktrees=True, name=self.name)

    async def start_task(self, task: TaskSpec) -> str:
        task_id = f"{self.name}-{uuid4().hex[:8]}"
        self._tasks[task_id] = _Task(task)
        return task_id

    def stream_events(self, task_id: str) -> AsyncGenerator[HarnessEvent, None]:
        return self._stream(task_id)

    async def _stream(self, task_id: str) -> AsyncGenerator[HarnessEvent, None]:
        task = self._require(task_id)
        yield HarnessEvent(type="started", message=task.spec.instruction)
        for message in task.messages:
            yield HarnessEvent(type="message", message=message)

    async def send_message(self, task_id: str, message: str) -> None:
        self._require(task_id).messages.append(message)

    async def get_result(self, task_id: str) -> HarnessResult:
        task = self._require(task_id)
        summary = task.summary if task.status == "ok" else "cancelled"
        return HarnessResult(status=task.status, summary=summary)

    async def cancel(self, task_id: str) -> None:
        self._require(task_id).status = "cancelled"

    async def usage(self, task_id: str) -> Usage:
        return self._require(task_id).usage

    def _require(self, task_id: str) -> _Task:
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise ContractError(f"unknown task {task_id}") from exc

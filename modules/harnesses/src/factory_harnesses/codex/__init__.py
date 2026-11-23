"""Codex harness. Calls openai-codex when OPENAI_API_KEY is set."""

import asyncio
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from factory_contracts import HarnessEvent, TaskSpec, Usage

from factory_harnesses.base import FixtureHarness

LiveRunner = Callable[[TaskSpec], Awaitable[Any]]


class CodexHarness(FixtureHarness):
    name = "codex"
    vendor = "openai"

    def __init__(self, runner: LiveRunner | None = None) -> None:
        super().__init__()
        self._runner = runner

    def _use_live(self) -> bool:
        return self._runner is not None or bool(os.environ.get("OPENAI_API_KEY"))

    async def start_task(self, task: TaskSpec) -> str:
        task_id = await super().start_task(task)
        self._tasks[task_id].live = self._use_live()  # type: ignore[attr-defined]
        return task_id

    async def _stream(self, task_id: str) -> AsyncIterator[HarnessEvent]:
        task = self._require(task_id)
        if not getattr(task, "live", False):
            async for event in super()._stream(task_id):
                yield event
            return
        timeout = int(os.environ.get("FACTORY_HARNESS_TIMEOUT", "600"))
        try:
            async with asyncio.timeout(timeout):
                result = await self._run(task.spec)
        except TimeoutError:
            task.status = "failed"
            yield HarnessEvent(type="error", message="harness timed out")
            return
        except asyncio.CancelledError:
            task.status = "cancelled"
            raise
        text = str(getattr(result, "final_response", None) or result)
        usage = getattr(result, "usage", None)
        tokens = int(getattr(usage, "total_tokens", 0) or 0)
        task.usage = Usage(tokens=tokens, usd=float(getattr(result, "cost_usd", 0) or 0))
        task.summary = text
        task.status = "ok"
        yield HarnessEvent(type="message", message=text)
        yield HarnessEvent(type="result", message=text)

    async def _run(self, spec: TaskSpec) -> Any:
        if self._runner is not None:
            return await self._runner(spec)
        attempts = int(os.environ.get("FACTORY_HARNESS_RETRIES", "2"))
        last: Exception | None = None
        for attempt in range(attempts + 1):
            try:
                return await _sdk_run(spec)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last = exc
                if attempt >= attempts:
                    break
                await asyncio.sleep(0.2 * (attempt + 1))
        raise RuntimeError(str(last or "codex call failed"))


async def _sdk_run(spec: TaskSpec) -> Any:
    from openai_codex import AsyncCodex, Sandbox

    async with AsyncCodex() as codex:
        if os.environ.get("OPENAI_API_KEY"):
            await _maybe_login(codex)
        thread = await codex.thread_start(sandbox=Sandbox.workspace_write)
        return await thread.run(spec.instruction)


async def _maybe_login(codex: Any) -> None:
    key = os.environ.get("OPENAI_API_KEY", "")
    login = getattr(codex, "login_api_key", None)
    if key and login is not None:
        result = login(key)
        if asyncio.iscoroutine(result):
            await result

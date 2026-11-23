"""Claude Code harness. Calls claude-agent-sdk when ANTHROPIC_API_KEY is set."""

import asyncio
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from factory_contracts import HarnessEvent, TaskSpec

from factory_harnesses.base import FixtureHarness, _Task

LiveRunner = Callable[[TaskSpec], Awaitable[AsyncIterator[Any]]]


class ClaudeHarness(FixtureHarness):
    name = "claude-code"
    vendor = "anthropic"

    def __init__(self, runner: LiveRunner | None = None) -> None:
        super().__init__()
        self._runner = runner

    def _use_live(self) -> bool:
        return self._runner is not None or bool(os.environ.get("ANTHROPIC_API_KEY"))

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
                async for event in self._live(task):
                    yield event
        except TimeoutError:
            task.status = "failed"
            task.summary = "harness timed out"
            yield HarnessEvent(type="error", message="harness timed out")

    async def _live(self, task: _Task) -> AsyncIterator[HarnessEvent]:
        attempts = int(os.environ.get("FACTORY_HARNESS_RETRIES", "2"))
        last_error = "claude call failed"
        for attempt in range(attempts + 1):
            try:
                if self._runner is not None:
                    stream = await self._runner(task.spec)
                else:
                    stream = _sdk_stream(task.spec)
                async for raw in stream:
                    event, usage = _map_claude(raw)
                    if usage is not None:
                        task.usage = usage
                    if event.type == "result":
                        task.summary = event.message
                        task.status = "failed" if event.message.startswith("error:") else "ok"
                    yield event
                return
            except asyncio.CancelledError:
                task.status = "cancelled"
                raise
            except Exception as exc:
                last_error = str(exc)
                if attempt >= attempts:
                    break
                await asyncio.sleep(0.2 * (attempt + 1))
        task.status = "failed"
        task.summary = last_error
        yield HarnessEvent(type="error", message=last_error)


def _sdk_stream(spec: TaskSpec) -> AsyncIterator[Any]:
    from claude_agent_sdk import ClaudeAgentOptions, query

    options = ClaudeAgentOptions(
        permission_mode="acceptEdits",
        cwd=spec.repo,
        allowed_tools=["Read", "Edit", "Bash", "Glob", "Grep"],
    )
    return query(prompt=spec.instruction, options=options)


def _map_claude(raw: Any) -> tuple[HarnessEvent, Any]:
    from factory_contracts import Usage

    text = getattr(raw, "result", None) or getattr(raw, "text", None)
    if text is None and hasattr(raw, "content"):
        parts = []
        for block in raw.content:
            piece = getattr(block, "text", None)
            if piece:
                parts.append(piece)
        text = "\n".join(parts)
    usage = None
    total = getattr(raw, "total_cost_usd", None)
    raw_usage = getattr(raw, "usage", None)
    if total is not None or isinstance(raw_usage, dict):
        tokens = 0
        if isinstance(raw_usage, dict):
            tokens = int(raw_usage.get("input_tokens", 0)) + int(raw_usage.get("output_tokens", 0))
        usage = Usage(usd=float(total or 0), tokens=tokens)
    kind = "result" if getattr(raw, "result", None) is not None or usage is not None else "message"
    if getattr(raw, "is_error", False):
        return HarnessEvent(type="result", message=f"error: {text or 'claude error'}"), usage
    return HarnessEvent(type=kind, message=str(text or raw)), usage

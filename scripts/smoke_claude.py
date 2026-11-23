"""Live smoke test for harness-claude-code. Requires ANTHROPIC_API_KEY."""

import asyncio
import os
import sys

from factory_contracts import TaskSpec
from factory_harnesses.claude import ClaudeHarness


async def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY to run the live Claude smoke test.", file=sys.stderr)
        return 2
    harness = ClaudeHarness()
    task_id = await harness.start_task(TaskSpec(instruction="Reply with the single word pong."))
    async for event in harness.stream_events(task_id):
        print(f"{event.type}: {event.message}")
    result = await harness.get_result(task_id)
    usage = await harness.usage(task_id)
    print(f"status={result.status} usd={usage.usd} tokens={usage.tokens}")
    return 0 if result.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

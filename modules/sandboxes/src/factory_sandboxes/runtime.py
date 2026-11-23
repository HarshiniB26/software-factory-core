"""Map a sandbox id to the command runner gates use for in-sandbox scans."""

from collections.abc import Callable
from typing import Any

from factory_contracts import ExecResult

Runner = Callable[[list[str]], ExecResult]
_RUNNERS: dict[str, Runner] = {}


def register(sandbox_id: str, runner: Runner) -> None:
    _RUNNERS[sandbox_id] = runner


def unregister(sandbox_id: str) -> None:
    _RUNNERS.pop(sandbox_id, None)


def run_command(sandbox_id: str, command: list[str]) -> ExecResult | None:
    runner = _RUNNERS.get(sandbox_id)
    if runner is None:
        return None
    return runner(command)


def registered(sandbox_id: str) -> bool:
    return sandbox_id in _RUNNERS


def clear() -> None:
    _RUNNERS.clear()


def note(sandbox_id: str) -> dict[str, Any]:
    return {"registered": sandbox_id in _RUNNERS}

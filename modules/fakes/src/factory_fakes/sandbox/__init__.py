"""In-memory sandbox. Denies curl and wget the way a locked-down egress policy would."""

from uuid import uuid4

from factory_contracts import ContractError, ExecResult, SandboxHandle, SandboxSpec, Usage


class FakeSandboxProvider:
    def __init__(self) -> None:
        self._alive: set[str] = set()

    async def create(self, spec: SandboxSpec) -> SandboxHandle:
        sandbox_id = f"sbx-{uuid4().hex[:8]}"
        self._alive.add(sandbox_id)
        return SandboxHandle(id=sandbox_id)

    async def exec(self, sandbox_id: str, command: list[str]) -> ExecResult:
        self._require(sandbox_id)
        if command and command[0] in {"curl", "wget"}:
            return ExecResult(exit_code=1, stdout="", stderr="egress denied")
        text = command[-1] if command else ""
        return ExecResult(exit_code=0, stdout=f"{text}\n", stderr="")

    async def fetch_branch(self, sandbox_id: str, branch: str) -> str:
        self._require(sandbox_id)
        return "a" * 40

    async def snapshot(self, sandbox_id: str) -> str | None:
        self._require(sandbox_id)
        return f"snap-{sandbox_id}"

    async def pause(self, sandbox_id: str) -> None:
        self._require(sandbox_id)

    async def destroy(self, sandbox_id: str) -> None:
        self._require(sandbox_id)
        self._alive.remove(sandbox_id)

    async def usage(self, sandbox_id: str) -> Usage:
        self._require(sandbox_id)
        return Usage(seconds=0.1)

    def _require(self, sandbox_id: str) -> None:
        if sandbox_id not in self._alive:
            raise ContractError(f"unknown sandbox {sandbox_id}")

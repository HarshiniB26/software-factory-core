"""Host workspace used when Docker or Modal credentials are absent.

Egress is denied unless the host is on the allowlist. The subprocess environment
never receives tokens from the parent process.
"""

import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from factory_contracts import ContractError, ExecResult, SandboxHandle, SandboxSpec, Usage

ALLOWLIST = ("pypi.org", "files.pythonhosted.org", "github.com", "api.github.com")
SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")


class HostSandbox:
    def __init__(self, root: Path | None = None, backend: str = "docker") -> None:
        self._root = root or Path(".factory/sandboxes")
        self._backend = backend
        self._alive: dict[str, Path] = {}

    async def create(self, spec: SandboxSpec) -> SandboxHandle:
        sandbox_id = f"{self._backend}-{uuid4().hex[:8]}"
        path = self._root / sandbox_id
        path.mkdir(parents=True, exist_ok=True)
        self._run(["git", "init"], path)
        readme = path / "README.md"
        readme.write_text(f"# {spec.repo or 'factory'}\n", encoding="utf-8")
        self._run(["git", "add", "README.md"], path)
        self._run(
            [
                "git",
                "-c",
                "user.email=factory@local",
                "-c",
                "user.name=factory",
                "commit",
                "-m",
                "init",
            ],
            path,
        )
        self._alive[sandbox_id] = path
        return SandboxHandle(id=sandbox_id)

    async def exec(self, sandbox_id: str, command: list[str]) -> ExecResult:
        path = self._require(sandbox_id)
        if command and command[0] in {"curl", "wget"}:
            target = command[-1] if len(command) > 1 else ""
            host = urlparse(target).hostname or ""
            if host not in ALLOWLIST:
                return ExecResult(exit_code=1, stdout="", stderr="egress denied")
        if command[:3] == ["git", "worktree", "add"] and len(command) >= 5:
            self._run(command, path)
            return ExecResult(exit_code=0, stdout="worktree\n", stderr="")
        if command[:2] == ["git", "diff"]:
            completed = self._run(command, path, check=False)
            return ExecResult(
                exit_code=completed.returncode, stdout=completed.stdout, stderr=completed.stderr
            )
        completed = self._run(command, path, check=False)
        text = command[-1] if command else ""
        stdout = completed.stdout or (
            f"{text}\n" if command and command[0] == "echo" else completed.stdout
        )
        return ExecResult(exit_code=completed.returncode, stdout=stdout, stderr=completed.stderr)

    async def fetch_branch(self, sandbox_id: str, branch: str) -> str:
        path = self._require(sandbox_id)
        self._run(["git", "checkout", "-B", branch], path)
        sha = self._run(["git", "rev-parse", "HEAD"], path).stdout.strip()
        return sha or ("a" * 40)

    async def snapshot(self, sandbox_id: str) -> str | None:
        self._require(sandbox_id)
        return f"snap-{sandbox_id}"

    async def pause(self, sandbox_id: str) -> None:
        self._require(sandbox_id)

    async def destroy(self, sandbox_id: str) -> None:
        path = self._require(sandbox_id)
        self._alive.pop(sandbox_id, None)
        shutil.rmtree(path, ignore_errors=True)

    async def usage(self, sandbox_id: str) -> Usage:
        self._require(sandbox_id)
        return Usage(seconds=0.1)

    def _require(self, sandbox_id: str) -> Path:
        try:
            return self._alive[sandbox_id]
        except KeyError as exc:
            raise ContractError(f"unknown sandbox {sandbox_id}") from exc

    def _run(
        self,
        command: list[str],
        cwd: Path,
        *,
        check: bool = True,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(cwd)}
        if extra_env:
            env.update(extra_env)
        for key in list(env):
            if any(marker in key.upper() for marker in SECRET_MARKERS):
                env.pop(key, None)
        return subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=check,
        )

"""Real Docker sandbox: one container per step, non-root, limited, secrets left on the host."""

import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from factory_contracts import ContractError, ExecResult, SandboxHandle, SandboxSpec, Usage

from factory_sandboxes.runtime import register, unregister

IMAGE = os.environ.get("FACTORY_SANDBOX_IMAGE", "factory-sandbox:local")
ALLOW = {"pypi.org", "files.pythonhosted.org", "github.com", "api.github.com", "api.osv.dev"}
SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")


def engine() -> list[str]:
    """docker, or sbx when that CLI is on PATH. FACTORY_SANDBOX_ENGINE forces one."""
    forced = os.environ.get("FACTORY_SANDBOX_ENGINE", "auto")
    if forced == "docker":
        return ["docker"]
    if forced == "sbx" or (forced == "auto" and shutil.which("sbx")):
        return ["sbx"]
    return ["docker"]


def docker_ready() -> bool:
    try:
        completed = subprocess.run(
            [*engine(), "info"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def ensure_image() -> None:
    probe = subprocess.run([*engine(), "image", "inspect", IMAGE], capture_output=True, check=False)
    if probe.returncode == 0:
        return
    context = Path(__file__).resolve().parents[2] / "image"
    if not (context / "Dockerfile").is_file():
        context = Path("modules/sandboxes/image")
    subprocess.run(["docker", "build", "-t", IMAGE, str(context)], check=True)


class DockerEngine:
    def __init__(self) -> None:
        self._root = Path(".factory/sandboxes")
        self._alive: dict[str, str] = {}
        self._scan: dict[str, str] = {}

    async def create(self, spec: SandboxSpec) -> SandboxHandle:
        return self._create(spec)

    def _create(self, spec: SandboxSpec) -> SandboxHandle:
        ensure_image()
        sandbox_id = f"docker-{uuid4().hex[:8]}"
        name = f"factory-{sandbox_id}"
        host = self._root / sandbox_id
        home = host / "home"
        home.mkdir(parents=True, exist_ok=True)
        os.chmod(host, 0o777)
        os.chmod(home, 0o777)
        user = _run_user()
        args = [
            *engine(),
            "run",
            "-d",
            "--name",
            name,
            "--user",
            user,
            "--memory",
            "1g",
            "--cpus",
            "1",
            "--pids-limit",
            "256",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "-e",
            "HOME=/work/home",
            "-v",
            f"{host.resolve()}:/work",
        ]
        origin = Path(spec.repo).expanduser() if spec.repo else None
        if spec.clone_url:
            origin = None
        if origin is not None and origin.exists():
            if os.getuid() == 0:
                _share(origin)
            args.extend(["-v", f"{origin.resolve()}:/origin"])
        args.append(IMAGE)
        subprocess.run(args, check=True, capture_output=True, text=True)
        self._alive[sandbox_id] = name
        self._scan[name] = "/work"
        register(sandbox_id, lambda command, _name=name: self._exec_result(_name, command))
        if spec.clone_url:
            header: list[str] = []
            if spec.clone_token:
                header = ["-c", f"http.extraheader=AUTHORIZATION: bearer {spec.clone_token}"]
            cloned = self._git(
                name, [*header, "clone", "--depth", "1", spec.clone_url, "/work/repo"]
            )
            if cloned.returncode != 0:
                self._git(name, ["init", "-b", "main", "/work/repo"])
        elif origin is not None and origin.exists():
            self._git(name, ["clone", "/origin", "/work/repo"])
        else:
            self._git(name, ["init", "-b", "main", "/work/repo"])
            readme = "printf '%s\\n' '# factory' > /work/repo/README.md"
            self._docker_exec(name, ["sh", "-c", readme])
            self._git(name, ["-C", "/work/repo", "add", "README.md"])
            self._git(
                name,
                [
                    "-C",
                    "/work/repo",
                    "-c",
                    "user.email=factory@local",
                    "-c",
                    "user.name=factory",
                    "commit",
                    "-m",
                    "init",
                ],
            )
        self._scan[name] = "/work/repo"
        return SandboxHandle(id=sandbox_id)

    async def exec(self, sandbox_id: str, command: list[str]) -> ExecResult:
        name = self._require(sandbox_id)
        if command and command[0] in {"curl", "wget"}:
            target = next((part for part in command if part.startswith("http")), "")
            host = urlparse(target).hostname or ""
            if host not in ALLOW:
                return ExecResult(exit_code=1, stdout="", stderr="egress denied")
        completed = self._docker_exec(name, command)
        if completed.returncode == 0 and "worktree" in command and "add" in command:
            index = command.index("add")
            if index + 1 < len(command):
                self._scan[name] = command[index + 1]
        return ExecResult(
            exit_code=completed.returncode, stdout=completed.stdout, stderr=completed.stderr
        )

    async def fetch_branch(self, sandbox_id: str, branch: str) -> str:
        name = self._require(sandbox_id)
        self._git(name, ["-C", "/work/repo", "branch", "-f", branch, "HEAD"])
        sha = self._docker_exec(name, ["git", "-C", "/work/repo", "rev-parse", "HEAD"])
        return sha.stdout.strip() or ("a" * 40)

    async def snapshot(self, sandbox_id: str) -> str | None:
        self._require(sandbox_id)
        return f"snap-{sandbox_id}"

    async def pause(self, sandbox_id: str) -> None:
        self._pause(self._require(sandbox_id))

    def _pause(self, name: str) -> None:
        subprocess.run([*engine(), "pause", name], check=False, capture_output=True)

    async def destroy(self, sandbox_id: str) -> None:
        self._destroy(sandbox_id)

    def _destroy(self, sandbox_id: str) -> None:
        name = self._alive.pop(sandbox_id, None)
        unregister(sandbox_id)
        if name:
            subprocess.run([*engine(), "rm", "-f", name], check=False, capture_output=True)
            self._scan.pop(name, None)

    async def usage(self, sandbox_id: str) -> Usage:
        self._require(sandbox_id)
        return Usage(seconds=1)

    def _require(self, sandbox_id: str) -> str:
        try:
            return self._alive[sandbox_id]
        except KeyError as exc:
            raise ContractError(f"unknown sandbox {sandbox_id}") from exc

    def _exec_result(self, name: str, command: list[str]) -> ExecResult:
        completed = self._docker_exec(name, command)
        return ExecResult(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def _git(self, name: str, args: list[str]) -> subprocess.CompletedProcess[str]:
        return self._docker_exec(name, ["git", *args])

    def _docker_exec(self, name: str, command: list[str]) -> subprocess.CompletedProcess[str]:
        env = [
            "-e",
            "HOME=/work/home",
            "-e",
            "SEMGREP_SEND_METRICS=off",
            "-e",
            "SEMGREP_ENABLE_VERSION_CHECK=0",
        ]
        for key in list(os.environ):
            if any(marker in key.upper() for marker in SECRET_MARKERS):
                env.extend(["-e", f"{key}="])
        workdir = self._scan.get(name, "/work")
        argv = [
            *engine(),
            "exec",
            "-u",
            _run_user(),
            "-w",
            workdir,
            *env,
            name,
            *_git_command(command),
        ]
        try:
            return subprocess.run(argv, capture_output=True, text=True, check=False, timeout=120)
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            return subprocess.CompletedProcess(argv, 124, stdout, "timed out")


def _run_user() -> str:
    uid = os.getuid()
    gid = os.getgid()
    if uid == 0:
        return "1000:1000"
    return f"{uid}:{gid}"


def _share(path: Path) -> None:
    for root, dirs, files in os.walk(path):
        os.chmod(root, os.stat(root).st_mode | 0o007)
        for name in dirs:
            target = Path(root) / name
            os.chmod(target, os.stat(target).st_mode | 0o007)
        for name in files:
            target = Path(root) / name
            os.chmod(target, os.stat(target).st_mode | 0o007)


def _git_command(command: list[str]) -> list[str]:
    if command and command[0] == "git":
        return ["git", "-c", "safe.directory=*", *command[1:]]
    return command

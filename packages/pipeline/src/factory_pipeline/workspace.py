"""Local single-tenant workspaces and checked subprocess execution."""

import asyncio
import os
import re
from pathlib import Path
from typing import Any

from factory_contracts import ContractError

REPO_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


async def command(
    args: list[str],
    cwd: str | Path | None = None,
    *,
    token: str | None = None,
    deadline: int = 120,
    include_stderr: bool = False,
) -> str:
    env = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT"}
    }
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if token:
        import base64

        credential = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env.update(
            {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "http.extraheader",
                "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {credential}",
            }
        )
    env["GIT_TERMINAL_PROMPT"] = "0"
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    try:
        out, err = await asyncio.wait_for(process.communicate(), deadline)
    except BaseException:
        import signal

        os.killpg(process.pid, signal.SIGKILL)
        await process.wait()
        raise
    if process.returncode:
        raise ContractError(f"{args[0]} {args[1]} failed with exit {process.returncode}")
    return (out + (err if include_stderr else b"")).decode().strip()


async def git(workspace: str | Path, *args: str, token: str | None = None) -> str:
    return await command(["git", *args], workspace, token=token)


async def prepare(
    target: str,
    base: str,
    destination: Path,
    token: str | None,
    *,
    bootstrap: bool = False,
    metadata: dict[str, Any] | None = None,
) -> str:
    await command(["git", "check-ref-format", "--branch", base])
    if await asyncio.to_thread(destination.exists):
        raise ContractError(
            "Workspace already exists; reconcile the prior preparation before retry"
        )
    await asyncio.to_thread(destination.parent.mkdir, parents=True, exist_ok=True)
    if REPO_NAME.fullmatch(target):
        if not token:
            raise ContractError("GitHub installation token is required for a live GitHub run")
        origin = f"https://github.com/{target}.git"
    else:
        local = await asyncio.to_thread(lambda: Path(target).expanduser().resolve())
        if not await asyncio.to_thread(local.is_dir):
            raise ContractError("Target must be an accessible local Git repository or owner/repo")
        origin = str(local)
    if bootstrap and not await command(["git", "ls-remote", "--", origin], token=token):
        await command(
            ["git", "clone", "--no-hardlinks", "--", origin, str(destination)], token=token
        )
        await git(destination, "symbolic-ref", "HEAD", f"refs/heads/{base}")
        await asyncio.to_thread(
            (destination / "README.md").write_text,
            "# New application\n\nFactory greenfield workspace.\n",
        )
        await git(destination, "add", "README.md")
        await git(
            destination,
            "-c",
            "user.name=Factory",
            "-c",
            "user.email=factory@local",
            "commit",
            "-m",
            "Initialize greenfield workspace",
        )
        if metadata is not None:
            metadata["base_initialization"] = {
                "branch": base,
                "sha": await git(destination, "rev-parse", "HEAD"),
            }
        return str(await asyncio.to_thread(destination.resolve))
    await command(
        [
            "git",
            "clone",
            "--no-hardlinks",
            "--single-branch",
            "--branch",
            base,
            "--",
            origin,
            str(destination),
        ],
        token=token,
    )
    await git(destination, "rev-parse", "HEAD")
    return str(await asyncio.to_thread(destination.resolve))


async def revision(workspace: str) -> str:
    """Fingerprint tracked edits and new files around a read-only agent turn."""
    import hashlib

    payload = [
        await git(workspace, "rev-parse", "HEAD"),
        await git(workspace, "diff", "--binary", "HEAD"),
    ]
    root = await asyncio.to_thread(Path(workspace).resolve)
    untracked = await git(workspace, "ls-files", "--others", "--exclude-standard", "-z")
    for name in untracked.split("\0"):
        if not name:
            continue
        path = await asyncio.to_thread((root / name).resolve)
        if not path.is_relative_to(root):
            raise ContractError("Untracked file points outside the worktree")
        contents = await asyncio.to_thread(path.read_bytes)
        payload.extend([name, hashlib.sha256(contents).hexdigest()])
    return hashlib.sha256("\0".join(payload).encode()).hexdigest()

"""One-command local start: compose, migrations, worker, API, console."""

import os
import shutil
import subprocess
from pathlib import Path

from factory_cli.doctor import docker_daemon


def start() -> None:
    root = Path.cwd()
    (root / ".factory").mkdir(exist_ok=True)
    if docker_daemon():
        subprocess.run(
            ["docker", "compose", "-f", "deploy/compose/docker-compose.yml", "up", "-d"],
            cwd=root,
            check=False,
        )
    url = os.environ.get("FACTORY_DATABASE_URL", "")
    if url.startswith("postgresql"):
        subprocess.run(
            ["uv", "run", "alembic", "-c", "packages/core/alembic.ini", "upgrade", "head"],
            cwd=root,
            check=True,
        )
    env = os.environ.copy()
    logs = root / ".factory"
    processes = [
        subprocess.Popen(
            ["uv", "run", "factory-worker"],
            cwd=root,
            env=env,
            stdout=(logs / "worker.log").open("ab"),
            stderr=subprocess.STDOUT,
        ),
        subprocess.Popen(
            ["uv", "run", "factory-api"],
            cwd=root,
            env=env,
            stdout=(logs / "api.log").open("ab"),
            stderr=subprocess.STDOUT,
        ),
    ]
    console = root / "frontend" / "console"
    if shutil.which("npm") and (console / "package.json").is_file():
        processes.append(
            subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=console,
                env=env,
                stdout=(logs / "console.log").open("ab"),
                stderr=subprocess.STDOUT,
            )
        )
    pids = "\n".join(str(proc.pid) for proc in processes) + "\n"
    (logs / "pids").write_text(pids, encoding="utf-8")
    print("API http://127.0.0.1:43123")
    print("Console http://127.0.0.1:43124")
    print(f"pids in {logs / 'pids'}")

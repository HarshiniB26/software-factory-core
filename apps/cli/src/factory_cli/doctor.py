"""Local environment checks. Nothing here contacts a model provider."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def report() -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    checks.append(("python", sys.version_info >= (3, 12), sys.version.split()[0]))
    git = shutil.which("git")
    checks.append(("git", bool(git), git or "not on PATH"))
    docker = docker_daemon()
    checks.append(("docker", docker, "daemon reachable" if docker else "daemon not reachable"))
    image = sandbox_image() if docker else False
    checks.append(
        (
            "sandbox-image",
            image or not docker,
            "factory-sandbox:local present" if image else "build with make sandbox-image",
        )
    )
    mode = os.environ.get("FACTORY_AUTH_MODE", "dev")
    if mode == "github":
        app_id = bool(os.environ.get("FACTORY_GITHUB_APP_ID"))
        key = bool(os.environ.get("FACTORY_GITHUB_APP_PRIVATE_KEY"))
        client_id = os.environ.get("FACTORY_GITHUB_CLIENT_ID")
        client_secret = os.environ.get("FACTORY_GITHUB_CLIENT_SECRET")
        checks.append(("github-app", app_id and key, "FACTORY_GITHUB_APP_ID and PRIVATE_KEY"))
        oauth_ok = bool(client_id and client_secret)
        checks.append(("github-oauth", oauth_ok, "OAuth client id and secret"))
    else:
        checks.append(("auth-mode", True, "dev login enabled"))
    litellm_url = os.environ.get("FACTORY_LITELLM_URL")
    litellm_key = os.environ.get("FACTORY_LITELLM_API_KEY")
    litellm = bool(litellm_url and litellm_key)
    checks.append(("litellm", litellm or mode == "dev", "proxy" if litellm else "fixture model"))
    anthropic = bool(os.environ.get("ANTHROPIC_API_KEY")) or mode == "dev"
    checks.append(("anthropic", anthropic, "ANTHROPIC_API_KEY"))
    openai = bool(os.environ.get("OPENAI_API_KEY")) or mode == "dev"
    checks.append(("openai", openai, "OPENAI_API_KEY"))
    temporal = os.environ.get("FACTORY_TEMPORAL_ADDRESS", "localhost:7233")
    checks.append(("temporal-address", True, temporal))
    root = Path(os.environ.get("FACTORY_REPO_ROOT", "."))
    config = root / ".factory" / "config.yaml"
    checks.append(("repo-config", config.is_file(), str(config)))
    return checks


def docker_daemon() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        completed = subprocess.run(["docker", "info"], capture_output=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def sandbox_image() -> bool:
    completed = subprocess.run(
        ["docker", "image", "inspect", "factory-sandbox:local"],
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0

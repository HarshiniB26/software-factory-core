"""GitHub user token, encrypted at rest, and the repos that token may list.

The plaintext token is never returned to the browser and never written to a log.
"""

import hashlib
import os
from base64 import urlsafe_b64encode
from typing import Any

import httpx
from cryptography.fernet import Fernet, InvalidToken
from factory_core import Database

ACCOUNT_PREFIX = "github.account:"
_HIDDEN = {"token", "access_token", "clone_token"}


def account_key(user_id: str) -> str:
    return f"{ACCOUNT_PREFIX}{user_id}"


def secret_key() -> str:
    return (
        os.environ.get("FACTORY_SECRET_KEY")
        or os.environ.get("FACTORY_SESSION_SECRET")
        or "dev-session-secret"
    )


def _fernet() -> Fernet:
    digest = hashlib.sha256(secret_key().encode()).digest()
    return Fernet(urlsafe_b64encode(digest))


def encrypt_token(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(blob: str) -> str:
    try:
        return _fernet().decrypt(blob.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("stored GitHub token could not be read") from exc


def install_url() -> str | None:
    slug = os.environ.get("FACTORY_GITHUB_APP_SLUG", "").strip()
    if not slug:
        return None
    return f"https://github.com/apps/{slug}/installations/new"


def public_repo(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if key not in _HIDDEN}


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "software-factory",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def github_json(client: httpx.AsyncClient, token: str, path: str) -> Any:
    response = await client.get(path, headers=_headers(token))
    if response.status_code >= 400:
        raise ValueError(f"GitHub {path} returned {response.status_code}")
    return response.json()


def _repo(item: dict[str, Any], installation_id: int) -> dict[str, Any]:
    owner = item.get("owner") or {}
    login = owner.get("login") if isinstance(owner, dict) else None
    full_name = str(item.get("full_name") or "")
    if not login and "/" in full_name:
        login = full_name.split("/", 1)[0]
    return {
        "owner": str(login or ""),
        "name": str(item.get("name") or ""),
        "full_name": full_name,
        "description": str(item.get("description") or ""),
        "path": None,
        "kind": "github",
        "private": bool(item.get("private")),
        "default_branch": str(item.get("default_branch") or "main"),
        "installation_id": installation_id,
    }


async def granted_repos(client: httpx.AsyncClient, token: str) -> tuple[bool, list[dict[str, Any]]]:
    payload = await github_json(client, token, "/user/installations")
    installations = payload.get("installations") if isinstance(payload, dict) else None
    if not isinstance(installations, list) or not installations:
        return False, []
    repos: list[dict[str, Any]] = []
    for installation in installations:
        if not isinstance(installation, dict) or not isinstance(installation.get("id"), int):
            continue
        installation_id = int(installation["id"])
        page = await github_json(
            client, token, f"/user/installations/{installation_id}/repositories"
        )
        raw = page.get("repositories") if isinstance(page, dict) else None
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, dict) and item.get("full_name"):
                repos.append(_repo(item, installation_id))
    return True, repos


async def profile_for(client: httpx.AsyncClient, token: str) -> dict[str, str]:
    payload = await github_json(client, token, "/user")
    if not isinstance(payload, dict):
        raise ValueError("GitHub /user returned an unexpected body")
    return {
        "login": str(payload.get("login") or payload.get("id") or ""),
        "avatar_url": str(payload.get("avatar_url") or ""),
    }


async def remember(
    database: Database,
    user_id: str,
    token: str,
    *,
    client: httpx.AsyncClient,
    profile: dict[str, str] | None = None,
) -> dict[str, Any]:
    who = profile or await profile_for(client, token)
    try:
        installed, repos = await granted_repos(client, token)
    except ValueError:
        installed, repos = False, []
    await database.put_state(
        account_key(user_id),
        {
            "login": who["login"],
            "avatar_url": who.get("avatar_url") or "",
            "token": encrypt_token(token),
            "installed": installed,
            "repos": repos,
        },
    )
    return {
        "login": who["login"],
        "avatar_url": who.get("avatar_url") or "",
        "installed": installed,
    }


async def load(database: Database, user_id: str) -> dict[str, Any] | None:
    stored = await database.get_state(account_key(user_id))
    if not stored or not isinstance(stored.get("token"), str):
        return None
    return stored


async def forget(database: Database, user_id: str) -> None:
    await database.put_state(account_key(user_id), {})


def github_public(stored: dict[str, Any] | None) -> dict[str, Any] | None:
    if not stored or not stored.get("login"):
        return None
    return {
        "login": str(stored["login"]),
        "avatar_url": str(stored.get("avatar_url") or ""),
        "installed": bool(stored.get("installed")),
    }


def cached_repos(stored: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not stored:
        return []
    repos = stored.get("repos") or []
    if not isinstance(repos, list):
        return []
    return [public_repo(item) for item in repos if isinstance(item, dict)]


async def list_branches(client: httpx.AsyncClient, token: str, full_name: str) -> list[str]:
    owner, _, name = full_name.partition("/")
    if not owner or not name:
        return []
    payload = await github_json(client, token, f"/repos/{owner}/{name}/branches")
    if not isinstance(payload, list):
        return []
    names: list[str] = []
    for item in payload:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(item["name"])
    return names


def http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url="https://api.github.com", timeout=20)

import json
from pathlib import Path

import httpx
import pytest
from factory_api.github_account import (
    decrypt_token,
    encrypt_token,
    forget,
    load,
    remember,
)
from factory_api.main import create_app
from factory_core import Database, connect, set_database
from factory_fakes.orchestrator import FakeOrchestrator
from httpx import ASGITransport, AsyncClient


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/user":
        return httpx.Response(
            200, json={"login": "ada", "avatar_url": "https://example.test/a.png"}
        )
    if path == "/user/installations":
        return httpx.Response(
            200, json={"installations": [{"id": 9, "account": {"login": "acme"}}]}
        )
    if path == "/user/installations/9/repositories":
        return httpx.Response(
            200,
            json={
                "repositories": [
                    {
                        "name": "billing",
                        "full_name": "acme/billing",
                        "private": True,
                        "default_branch": "main",
                        "description": "Checkout",
                        "owner": {"login": "acme"},
                    }
                ]
            },
        )
    if path == "/repos/acme/billing/branches":
        return httpx.Response(200, json=[{"name": "main"}, {"name": "release"}])
    return httpx.Response(404, json={"message": "missing"})


def _github() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(_handler),
        base_url="https://api.github.com",
    )


def test_token_round_trip_does_not_keep_plaintext() -> None:
    blob = encrypt_token("gho_test_token")
    assert "gho_test_token" not in blob
    assert decrypt_token(blob) == "gho_test_token"


@pytest.fixture
async def database(tmp_path: Path):
    store = await connect(
        f"sqlite+aiosqlite:///{tmp_path}/factory.db",
        blob_root=tmp_path / "blobs",
    )
    set_database(store)
    try:
        yield store
    finally:
        await store.dispose()


async def test_repos_lists_granted_github_repos_without_the_token(database: Database) -> None:
    app = create_app(database, FakeOrchestrator())
    app.state.github_http = _github()
    async with _github() as client:
        await remember(database, "local", "gho_test_token", client=client)
    stored = await load(database, "local")
    assert stored is not None
    assert "gho_test_token" not in json.dumps(stored)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as api:
        listed = await api.get("/repos")
        assert listed.status_code == 200
        body = listed.json()
        assert "gho_test_token" not in listed.text
        names = [item["full_name"] for item in body["repos"]]
        assert names[0] == "local/sample"
        assert "acme/billing" in names
        billing = next(item for item in body["repos"] if item["full_name"] == "acme/billing")
        assert billing["private"] is True
        assert billing["default_branch"] == "main"
        assert billing["kind"] == "github"
        assert body["github"]["login"] == "ada"
        assert body["github"]["installed"] is True
        connected = await api.post(
            "/repos/connect",
            json={"full_name": "acme/billing", "branch": "release"},
        )
        assert connected.status_code == 200
        assert connected.json()["branch"] == "release"
        assert "token" not in connected.json()
        branches = await api.get("/repos/branches", params={"full_name": "acme/billing"})
        assert branches.status_code == 200
        assert branches.json()["branches"] == ["main", "release"]
        assert branches.json()["default"] == "main"
        refreshed = await api.get("/repos/github/refresh")
        assert refreshed.status_code == 200
        assert "acme/billing" in [item["full_name"] for item in refreshed.json()["repos"]]
        disconnected = await api.post("/repos/disconnect", json={"full_name": "acme/billing"})
        assert disconnected.status_code == 200
        account = await api.post("/auth/github/disconnect")
        assert account.status_code == 200
    await forget(database, "local")
    assert await load(database, "local") is None


def test_missing_app_key_does_not_mint_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FACTORY_GITHUB_APP_ID", raising=False)
    monkeypatch.delenv("FACTORY_GITHUB_APP_PRIVATE_KEY", raising=False)
    from factory_vcs_github.install import installation_token  # pyright: ignore[reportMissingTypeStubs]

    assert installation_token(9) is None


def test_install_url_uses_the_app_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    from factory_api.github_account import install_url

    monkeypatch.setenv("FACTORY_GITHUB_APP_SLUG", "factory")
    assert install_url() == "https://github.com/apps/factory/installations/new"
    monkeypatch.delenv("FACTORY_GITHUB_APP_SLUG")
    assert install_url() is None


async def test_empty_installations_stay_signed_in(database: Database) -> None:
    def empty(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user":
            return httpx.Response(200, json={"login": "ada", "avatar_url": ""})
        if request.url.path == "/user/installations":
            return httpx.Response(200, json={"installations": []})
        return httpx.Response(404)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(empty), base_url="https://api.github.com"
    )
    saved = await remember(database, "local", "gho_test_token", client=client)
    await client.aclose()
    assert saved["installed"] is False
    stored = await load(database, "local")
    assert stored is not None
    assert stored["repos"] == []

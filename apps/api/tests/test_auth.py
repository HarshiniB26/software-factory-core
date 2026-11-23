import os
from collections.abc import AsyncIterator
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from factory_api.main import create_app
from factory_core import Database, connect, set_database
from factory_fakes.orchestrator import FakeOrchestrator
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def database(tmp_path: Path) -> AsyncIterator[Database]:
    store = await connect(
        f"sqlite+aiosqlite:///{tmp_path}/factory.db",
        blob_root=tmp_path / "blobs",
    )
    set_database(store)
    try:
        yield store
    finally:
        await store.dispose()


def _pem_pair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private, public


async def test_dev_login_is_rejected_outside_dev_mode(
    database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FACTORY_AUTH_MODE", "github")
    app = create_app(database, FakeOrchestrator())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        denied = await client.post("/auth/dev-login", json={"user": "ada", "role": "requester"})
        unsigned = await client.get("/auth/me")
        missing = await client.get("/auth/github/login")
    assert denied.status_code == 403
    assert unsigned.status_code == 401
    assert missing.status_code == 503


async def test_cloudflare_access_jwt_sets_roles(
    database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    private, public = _pem_pair()
    monkeypatch.setenv("FACTORY_AUTH_MODE", "github")
    monkeypatch.setenv("FACTORY_CF_ACCESS_AUD", "factory")
    monkeypatch.setenv("FACTORY_CF_ACCESS_PEM", public)
    monkeypatch.setenv("FACTORY_ADMIN_USERS", "ada@example.com")
    token = jwt.encode(
        {"email": "ada@example.com", "aud": "factory"},
        private,
        algorithm="RS256",
    )
    app = create_app(database, FakeOrchestrator())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/auth/me", headers={"cf-access-jwt-assertion": token})
    assert response.status_code == 200
    assert response.json()["id"] == "ada@example.com"
    assert "admin" in response.json()["roles"]
    os.environ.pop("FACTORY_AUTH_MODE", None)

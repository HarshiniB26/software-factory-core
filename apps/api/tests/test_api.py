import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

import pytest
from factory_api.main import create_app
from factory_contracts import TASK_QUEUE
from factory_core import Database, connect, set_database
from factory_fakes.orchestrator import FakeOrchestrator
from factory_orchestrator_temporal import TemporalOrchestrator
from factory_worker.activities import mark_completed, mark_started, pipeline_tick
from factory_worker.workflows import FactoryRequestWorkflow
from httpx import ASGITransport, AsyncClient
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker


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


async def test_dev_connects_the_sample_repo(database: Database) -> None:
    app = create_app(database, FakeOrchestrator())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        listed = await client.get("/repos")
        assert listed.status_code == 200
        names = [item["full_name"] for item in listed.json()["repos"]]
        assert "local/sample" in names
        connected = await client.post("/repos/connect", json={"full_name": "local/sample"})
        assert connected.status_code == 200
        assert connected.json()["path"].endswith("examples/sample-repo")
        missing = await client.post("/repos/connect", json={"full_name": "nope/missing"})
        assert missing.status_code == 404
        created = await client.post(
            "/requests",
            json={"title": "Add health", "body": "Add a health check"},
        )
        assert created.status_code == 201
        assert str(created.json()["target"]).endswith("examples/sample-repo")


async def test_health_and_list(database: Database) -> None:
    app = create_app(database, FakeOrchestrator())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        listed = await client.get("/requests")
        assert listed.status_code == 200
        assert listed.json() == []


async def test_create_runs_workflow_and_streams_events(database: Database) -> None:
    async with await WorkflowEnvironment.start_time_skipping() as env:
        orchestrator = TemporalOrchestrator(env.client, task_queue=TASK_QUEUE)
        app = create_app(database, orchestrator)
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[FactoryRequestWorkflow],
            activities=[mark_started, mark_completed, pipeline_tick],
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                created = await client.post(
                    "/requests",
                    json={"title": "Add health", "body": "Add GET /health"},
                )
                assert created.status_code == 201
                request_id = created.json()["id"]
                history = await _wait_for_history(client, request_id)
                listed = await client.get("/requests")
            body = await asyncio.wait_for(_read_sse(app, request_id), timeout=5)
    types = [str(item["type"]) for item in history]
    assert types[0] == "request.created"
    assert "workflow.started" in types
    assert "pr.opened" in types
    assert "workflow.completed" in types
    assert "request.created" in body
    assert "workflow.started" in body
    assert "workflow.completed" in body
    assert listed.status_code == 200
    assert listed.json()[0]["status"] == "completed"
    stored = await database.get_request(UUID(request_id))
    assert stored is not None
    assert stored.status == "completed"


async def _wait_for_history(client: AsyncClient, request_id: str) -> list[dict[str, object]]:
    last: list[dict[str, object]] = []
    for _ in range(50):
        response = await client.get(f"/requests/{request_id}/events/history")
        assert response.status_code == 200
        payload = response.json()
        assert isinstance(payload, list)
        last = payload
        if any(item.get("type") == "workflow.completed" for item in payload):
            return payload
        await asyncio.sleep(0.1)
    raise AssertionError(last)


async def _read_sse(app: object, request_id: str) -> str:
    """Read the SSE response until the completed event, then disconnect.

    httpx's ASGI transport buffers until the app returns, and this stream stays
    open, so the test drives the ASGI app directly.
    """
    chunks: list[bytes] = []
    done = asyncio.Event()
    sent_request = False

    async def receive() -> dict[str, object]:
        nonlocal sent_request
        if not sent_request:
            sent_request = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await done.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, object]) -> None:
        if message.get("type") != "http.response.body":
            return
        body = message.get("body", b"")
        if isinstance(body, bytes):
            chunks.append(body)
        if b"workflow.completed" in b"".join(chunks):
            done.set()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": f"/requests/{request_id}/events",
        "raw_path": f"/requests/{request_id}/events".encode(),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }
    await app(scope, receive, send)  # type: ignore[operator]
    return b"".join(chunks).decode()

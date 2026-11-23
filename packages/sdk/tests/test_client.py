from datetime import UTC, datetime
from uuid import uuid4

import httpx
from factory_sdk import FactoryClient


def test_client_reads_health_and_requests() -> None:
    request_id = uuid4()
    created = datetime.now(UTC).isoformat()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok", "service": "factory-api"})
        if request.method == "POST":
            return httpx.Response(
                201,
                json={
                    "id": str(request_id),
                    "title": "Add health",
                    "body": "Add GET /health",
                    "target": None,
                    "requester": "local",
                    "status": "created",
                    "created_at": created,
                },
            )
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(request_id),
                    "title": "Add health",
                    "body": "Add GET /health",
                    "target": None,
                    "requester": "local",
                    "status": "created",
                    "created_at": created,
                }
            ],
        )

    with FactoryClient(
        "http://factory.test", client=httpx.Client(transport=httpx.MockTransport(handler))
    ) as client:
        assert client.health()["status"] == "ok"
        created_request = client.create_request("Add health", "Add GET /health")
        assert created_request.id == request_id
        assert client.list_requests()[0].title == "Add health"

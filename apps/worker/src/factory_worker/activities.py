"""Activities that append workflow events. They run outside the workflow sandbox."""

import asyncio
from contextlib import suppress
from typing import Any
from uuid import UUID

from factory_contracts import ORCHESTRATOR_MODULE, EventDraft
from factory_core import get_database
from factory_pipeline import tick
from temporalio import activity


@activity.defn(name="mark_started")
async def mark_started(request_id: str) -> None:
    database = get_database()
    request = UUID(request_id)
    await database.update_status(request, "running")
    await database.append(
        EventDraft(
            request_id=request,
            type="workflow.started",
            module=ORCHESTRATOR_MODULE,
            payload={"workflow": "FactoryRequestWorkflow"},
        )
    )


@activity.defn(name="pipeline_tick")
async def pipeline_tick(payload: dict[str, Any]) -> dict[str, Any]:
    request_id = UUID(str(payload["request_id"]))

    async def pulse() -> None:
        while True:
            activity.heartbeat({"request_id": str(request_id)})
            await asyncio.sleep(10)

    heartbeat = asyncio.create_task(pulse())
    try:
        return await tick(request_id, payload)
    finally:
        heartbeat.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat


@activity.defn(name="mark_completed")
async def mark_completed(request_id: str) -> None:
    database = get_database()
    request = UUID(request_id)
    current = await database.get_request(request)
    if current is None or current.status not in {"failed", "killed"}:
        await database.update_status(request, "completed")
    await database.append(
        EventDraft(
            request_id=request,
            type=(
                "workflow.completed"
                if current and current.status not in {"failed", "killed"}
                else f"workflow.{current.status if current else 'failed'}"
            ),
            module=ORCHESTRATOR_MODULE,
            payload={
                "status": current.status
                if current and current.status in {"failed", "killed"}
                else "completed"
            },
        )
    )

"""Temporal client that satisfies the Orchestrator protocol.

The worker registers the workflow. This module only starts, signals, queries,
cancels, and schedules it, so the API does not import the worker.
"""

from typing import Any
from uuid import uuid4

from factory_contracts import TASK_QUEUE
from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleSpec,
)


class TemporalOrchestrator:
    def __init__(self, client: Client, task_queue: str = TASK_QUEUE) -> None:
        self._client = client
        self._task_queue = task_queue

    @classmethod
    async def from_settings(cls, settings: dict[str, Any] | None = None) -> "TemporalOrchestrator":
        cfg = settings or {}
        client = await Client.connect(
            str(cfg.get("address", "localhost:7233")),
            namespace=str(cfg.get("namespace", "default")),
        )
        return cls(client, task_queue=str(cfg.get("task_queue", TASK_QUEUE)))

    async def start_workflow(self, workflow: str, payload: dict[str, Any], workflow_id: str) -> str:
        handle = await self._client.start_workflow(
            workflow,
            payload,
            id=workflow_id,
            task_queue=self._task_queue,
        )
        return handle.id

    async def signal(self, workflow_id: str, signal: str, payload: dict[str, Any]) -> None:
        handle = self._client.get_workflow_handle(workflow_id)
        await handle.signal(signal, payload)

    async def query(self, workflow_id: str, query: str) -> dict[str, Any]:
        handle = self._client.get_workflow_handle(workflow_id)
        result: Any = await handle.query(query)
        if isinstance(result, dict):
            return result
        return {"value": result}

    async def cancel(self, workflow_id: str) -> None:
        handle = self._client.get_workflow_handle(workflow_id)
        await handle.cancel()

    async def schedule(self, workflow: str, cron: str, payload: dict[str, Any]) -> str:
        schedule_id = f"schedule-{uuid4()}"
        await self._client.create_schedule(
            schedule_id,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    workflow,
                    payload,
                    id=f"{schedule_id}-run",
                    task_queue=self._task_queue,
                ),
                spec=ScheduleSpec(cron_expressions=[cron]),
            ),
        )
        return schedule_id

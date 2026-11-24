"""Independent monitor and bounded evaluation-job executor."""

import asyncio
import logging
import time
from contextlib import suppress
from typing import Any
from uuid import UUID, uuid4

from factory_core import Settings, connect, set_database
from factory_pipeline.ci import scan as scan_ci
from factory_pipeline.learning import evaluate
from factory_pipeline.supervision import watchdog
from temporalio.client import Client


async def serve() -> None:
    settings = Settings()
    database = await connect(settings.database_url, settings.blob_root)
    set_database(database)

    async def restart(request_id: UUID) -> None:
        client = await Client.connect(
            settings.temporal_address, namespace=settings.temporal_namespace
        )
        await client.start_workflow(
            "FactoryRequestWorkflow",
            {"request_id": str(request_id)},
            id=f"request-{request_id}",
            task_queue=settings.temporal_task_queue,
        )

    owner = str(uuid4())
    evaluation_task: asyncio.Task[None] | None = None
    ci_task: asyncio.Task[None] | None = None
    current_job: dict[str, Any] | None = None

    async def run_job(job: dict[str, Any]) -> None:
        try:
            result = await evaluate(database, job["candidate_id"])
            final = {"status": "completed", "evaluation_id": result["id"]}
        except Exception as exc:
            final = {"status": "failed", "error": type(exc).__name__}
        existing = await database.get_state(f"learning:job:{job['id']}")
        if existing and existing.get("owner") == owner and existing["status"] == "running":
            await database.compare_state(
                f"learning:job:{job['id']}", existing, {**existing, **final}
            )

    try:
        while True:
            try:
                alerts = await watchdog(database)
                if ci_task is None or ci_task.done():
                    ci_task = asyncio.create_task(scan_ci(database, restart))
                jobs = await database.list_states("learning:job:")
                if evaluation_task and not evaluation_task.done() and current_job:
                    key = f"learning:job:{current_job['id']}"
                    existing = await database.get_state(key)
                    if (
                        existing
                        and existing.get("owner") == owner
                        and existing["status"] == "running"
                    ):
                        await database.compare_state(key, existing, {**existing, "at": time.time()})
                    else:
                        evaluation_task.cancel()
                else:
                    queued = next((job for job in jobs if job["status"] == "queued"), None)
                    if queued:
                        running = {**queued, "status": "running", "owner": owner, "at": time.time()}
                        if await database.compare_state(
                            f"learning:job:{queued['id']}", queued, running
                        ):
                            current_job = running
                            evaluation_task = asyncio.create_task(run_job(running))
                for job in jobs:
                    if job["status"] == "running" and time.time() - job["at"] > 90:
                        await database.compare_state(
                            f"learning:job:{job['id']}",
                            job,
                            {**job, "status": "failed", "error": "Evaluator heartbeat expired"},
                        )
                if alerts:
                    logging.warning("factory monitor: %d requests require attention", len(alerts))
            except Exception:
                logging.exception("factory monitor scan failed")
            await asyncio.sleep(15)
    finally:
        if ci_task:
            ci_task.cancel()
            with suppress(asyncio.CancelledError):
                await ci_task
        if evaluation_task:
            evaluation_task.cancel()
            with suppress(asyncio.CancelledError):
                await evaluation_task
        await database.dispose()


def main() -> None:
    asyncio.run(serve())

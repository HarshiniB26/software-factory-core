from datetime import timedelta

import pytest
from factory_worker.workflows import FactoryRequestWorkflow
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker


@pytest.mark.parametrize("terminal", ["failed", "killed", "completed"])
async def test_workflow_preserves_pipeline_terminal_status(terminal: str) -> None:
    @activity.defn(name="mark_started")
    async def started(_request_id: str) -> None:
        pass

    @activity.defn(name="mark_completed")
    async def finished(_request_id: str) -> None:
        pass

    @activity.defn(name="pipeline_tick")
    async def tick(_payload: dict[str, str]) -> dict[str, str]:
        activity.heartbeat("running")
        return {"status": terminal}

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="terminal-test",
            workflows=[FactoryRequestWorkflow],
            activities=[started, finished, tick],
        ),
    ):
        handle = await env.client.start_workflow(
            FactoryRequestWorkflow.run,
            {"request_id": "terminal-test"},
            id=f"terminal-{terminal}",
            task_queue="terminal-test",
            execution_timeout=timedelta(seconds=30),
        )
        assert await handle.result() == terminal
        assert await handle.query(FactoryRequestWorkflow.status) == {"status": terminal}

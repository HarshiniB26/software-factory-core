import asyncio

from factory_contracts import TASK_QUEUE
from factory_core import Settings, connect, set_database
from temporalio.client import Client
from temporalio.worker import Worker

from factory_worker.activities import mark_completed, mark_started, pipeline_tick
from factory_worker.workflows import FactoryRequestWorkflow, NoOpRequestWorkflow


async def serve() -> None:
    settings = Settings()
    set_database(await connect(settings.database_url, settings.blob_root))
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue or TASK_QUEUE,
        workflows=[FactoryRequestWorkflow, NoOpRequestWorkflow],
        activities=[mark_started, mark_completed, pipeline_tick],
    )
    await worker.run()


def main() -> None:
    asyncio.run(serve())

"""Deterministic workflow. Activities live in another module so this file stays pure."""

from datetime import timedelta

from temporalio import workflow

# Name matches factory_contracts.NOOP_WORKFLOW. Kept as a literal so this module
# does not import Pydantic into the Temporal sandbox.
_WORKFLOW_NAME = "NoOpRequestWorkflow"


@workflow.defn(name="FactoryRequestWorkflow")
class FactoryRequestWorkflow:
    def __init__(self) -> None:
        self._status = "running"
        self._answer: str | None = None
        self._decision: str | None = None

    @workflow.run
    async def run(self, payload: dict[str, str]) -> str:
        request_id = payload["request_id"]
        await workflow.execute_activity(
            "mark_started",
            request_id,
            start_to_close_timeout=timedelta(seconds=30),
        )
        hint: dict[str, str] = {"request_id": request_id}
        if payload.get("overrides"):
            hint["overrides"] = payload["overrides"]
        if payload.get("revises"):
            hint["revises"] = payload["revises"]
        if payload.get("parent_id"):
            hint["parent_id"] = payload["parent_id"]
        while True:
            result = await workflow.execute_activity(
                "pipeline_tick",
                hint,
                start_to_close_timeout=timedelta(minutes=5),
            )
            status = str(result.get("status", ""))
            self._status = status
            if status == "parked":
                try:
                    await workflow.wait_condition(
                        lambda: self._answer is not None,
                        timeout=timedelta(days=3),
                    )
                except TimeoutError:
                    hint = {"request_id": request_id, "timeout": "1"}
                else:
                    hint = {"request_id": request_id, "answer": self._answer or ""}
                self._answer = None
                continue
            if status == "awaiting_approval":
                try:
                    await workflow.wait_condition(
                        lambda: self._decision is not None,
                        timeout=timedelta(days=3),
                    )
                except TimeoutError:
                    hint = {"request_id": request_id, "timeout": "1"}
                else:
                    hint = {"request_id": request_id, "decision": self._decision or ""}
                self._decision = None
                continue
            break
        await workflow.execute_activity(
            "mark_completed",
            request_id,
            start_to_close_timeout=timedelta(seconds=30),
        )
        self._status = "completed"
        return "completed"

    @workflow.signal(name="answer")
    async def answer(self, payload: dict[str, str]) -> None:
        self._answer = payload.get("text", "")

    @workflow.signal(name="decide")
    async def decide(self, payload: dict[str, str]) -> None:
        self._decision = payload.get("decision", "")

    @workflow.query(name="status")
    def status(self) -> dict[str, str]:
        return {"status": self._status}


@workflow.defn(name=_WORKFLOW_NAME)
class NoOpRequestWorkflow:
    def __init__(self) -> None:
        self._status = "running"

    @workflow.run
    async def run(self, payload: dict[str, str]) -> str:
        request_id = payload["request_id"]
        await workflow.execute_activity(
            "mark_started",
            request_id,
            start_to_close_timeout=timedelta(seconds=30),
        )
        await workflow.execute_activity(
            "mark_completed",
            request_id,
            start_to_close_timeout=timedelta(seconds=30),
        )
        self._status = "completed"
        return "completed"

    @workflow.query(name="status")
    def status(self) -> dict[str, str]:
        return {"status": self._status}

    @workflow.signal(name="ping")
    async def ping(self, payload: dict[str, str]) -> None:
        value = payload.get("status")
        if value:
            self._status = value

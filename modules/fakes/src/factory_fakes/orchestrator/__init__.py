"""Records workflow calls. It does not talk to Temporal."""

from typing import Any

from factory_contracts import ContractError


class FakeOrchestrator:
    def __init__(self) -> None:
        self._runs: dict[str, dict[str, Any]] = {}
        self._schedules: dict[str, dict[str, Any]] = {}

    async def start_workflow(self, workflow: str, payload: dict[str, Any], workflow_id: str) -> str:
        self._runs[workflow_id] = {
            "status": "running",
            "workflow": workflow,
            "payload": dict(payload),
        }
        return workflow_id

    async def signal(self, workflow_id: str, signal: str, payload: dict[str, Any]) -> None:
        run = self._require(workflow_id)
        if signal == "ping":
            run["status"] = str(payload.get("status", "signaled"))

    async def query(self, workflow_id: str, query: str) -> dict[str, Any]:
        run = self._require(workflow_id)
        if query != "status":
            raise ContractError(f"unknown query {query}")
        return {"status": str(run["status"])}

    async def cancel(self, workflow_id: str) -> None:
        self._require(workflow_id)["status"] = "cancelled"

    async def schedule(self, workflow: str, cron: str, payload: dict[str, Any]) -> str:
        schedule_id = f"schedule-{len(self._schedules) + 1}"
        self._schedules[schedule_id] = {
            "workflow": workflow,
            "cron": cron,
            "payload": dict(payload),
        }
        return schedule_id

    def _require(self, workflow_id: str) -> dict[str, Any]:
        try:
            return self._runs[workflow_id]
        except KeyError as exc:
            raise ContractError(f"unknown workflow {workflow_id}") from exc

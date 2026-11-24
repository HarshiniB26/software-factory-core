"""Administrative supervision and measured improvement operations."""

import time
from typing import Any, Literal
from uuid import UUID, uuid4

from factory_contracts import ContractError
from factory_core import Settings
from factory_pipeline.learning import enhancement, promote
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from factory_api.console_api import principal, require_role

router = APIRouter()


def admin(request: Request) -> Any:
    actor = principal(request)
    require_role(actor, "admin")
    return request.app.state.database


class Promotion(BaseModel):
    evaluation_id: str


@router.get("/monitor")
async def monitoring(request: Request) -> dict[str, Any]:
    database = admin(request)
    health = await database.get_state("monitor.health")
    alerts = await database.list_states("alert:")
    return {
        "health": health,
        "healthy": bool(health and time.time() - health["at"] < 60),
        "alerts": [item for item in alerts if item.get("requires_action")],
    }


@router.get("/runtime")
async def runtime(request: Request) -> dict[str, Any]:
    principal(request)
    import os

    from factory_pipeline.autonomous import selected

    settings = await request.app.state.database.get_state("runtime.settings") or {}
    provider = settings.get("provider") or os.environ.get("FACTORY_T3_PROVIDER")
    model = settings.get("model") or os.environ.get("FACTORY_T3_MODEL")
    try:
        catalog = await (await selected("harness-t3")).catalog()
        ready = any(
            item["id"] == provider and item["enabled"] and model in item["models"]
            for item in catalog
        )
    except Exception:
        catalog, ready = [], False
    return {
        "execution_mode": Settings().execution_mode,
        "provider": provider,
        "model": model,
        "providers": catalog,
        "ready": ready,
        "usage_available": False,
        "execution_isolation": "trusted-host",
        "approval": settings.get("approval", "high_risk"),
    }


class RuntimeSelection(BaseModel):
    provider: str
    model: str
    approval: Literal["high_risk", "always"] = "high_risk"


@router.put("/runtime")
async def select_runtime(body: RuntimeSelection, request: Request) -> dict[str, Any]:
    database = admin(request)
    from factory_pipeline.autonomous import selected

    catalog = await (await selected("harness-t3")).catalog()
    if not any(
        item["id"] == body.provider and item["enabled"] and body.model in item["models"]
        for item in catalog
    ):
        raise HTTPException(status_code=422, detail="Choose an available provider and model")
    await database.put_state("runtime.settings", body.model_dump())
    return await runtime(request)


@router.get("/learning")
async def learning(request: Request) -> dict[str, Any]:
    database = admin(request)
    return {
        "outcomes": await database.list_states("learning:outcome:"),
        "candidates": await database.list_states("learning:candidate:"),
        "evaluations": await database.list_states("learning:evaluation:"),
        "active": await database.list_states("learning:active:"),
        "jobs": await database.list_states("learning:job:"),
    }


@router.post("/learning/{candidate_id}/evaluate", status_code=202)
async def evaluate_candidate(candidate_id: str, request: Request) -> dict[str, Any]:
    database = admin(request)
    import os

    if not os.environ.get("FACTORY_EVAL_SUITE"):
        raise HTTPException(
            status_code=409, detail="No trusted held-out evaluation suite configured"
        )
    if not await database.get_state(f"learning:candidate:{candidate_id}"):
        raise HTTPException(status_code=404, detail="Candidate not found")
    job = {"id": str(uuid4()), "candidate_id": candidate_id, "status": "queued", "at": time.time()}
    await database.insert_state(f"learning:job:{job['id']}", job)
    return job


@router.post("/learning/{candidate_id}/promote")
async def activate(candidate_id: str, body: Promotion, request: Request) -> dict[str, Any]:
    database = admin(request)
    try:
        return await promote(database, candidate_id, body.evaluation_id, principal(request).id)
    except ContractError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/learning/{profile}/rollback")
async def rollback(profile: str, request: Request) -> dict[str, Any]:
    database = admin(request)
    key = f"learning:active:{profile}"
    active = await database.get_state(key)
    if not active:
        raise HTTPException(status_code=404, detail="No active candidate")
    await enhancement(database, profile, active.get("previous"))
    revision = {
        "candidate_id": active.get("previous"),
        "previous": active.get("candidate_id"),
        "approved_by": principal(request).id,
        "activated_at": time.time(),
        "rollback": True,
    }
    if not await database.compare_state(key, active, revision):
        raise HTTPException(status_code=409, detail="Active candidate changed; refresh and retry")
    await database.insert_state(f"learning:activation:{uuid4()}", revision)
    return revision


@router.post("/monitor/alerts/{request_id}/acknowledge")
async def acknowledge(request_id: UUID, request: Request) -> dict[str, bool]:
    database = admin(request)
    for reason in ("stale_run", "uncertain_operation", "no_progress", "ci_failed"):
        key = f"alert:{request_id}:{reason}"
        alert = await database.get_state(key)
        if alert:
            alert.update({"requires_action": False, "acknowledged_by": principal(request).id})
            await database.put_state(key, alert)
    return {"acknowledged": True}


@router.post("/requests/{request_id}/recover", status_code=202)
async def recover(request_id: UUID, request: Request) -> dict[str, Any]:
    database = admin(request)
    from factory_contracts import FACTORY_WORKFLOW
    from factory_pipeline.autonomous import selected

    owner = str(uuid4())
    lease = f"lease:run:{request_id}"
    if not await database.acquire_lease(lease, owner):
        raise HTTPException(status_code=409, detail="A worker still owns this run")
    try:
        state = await database.get_state(f"run:{request_id}") or {}
        stage = state.get("pending_operation")
        if not stage:
            raise HTTPException(status_code=409, detail="No uncertain operation to reconcile")
        if stage != "publish":
            if not state.get("thread_id") or not state.get("operation_marker"):
                raise HTTPException(
                    status_code=409, detail="Unknown launch; reconcile in T3 manually"
                )
            try:
                await (await selected("harness-t3")).recover_operation(
                    state["thread_id"], state["operation_marker"], state.get("session_response", "")
                )
            except ContractError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        state["live_stage"] = stage
        state.pop("outcome", None)
        state.pop("failure", None)
        await database.put_fenced_state(f"run:{request_id}", state, lease, owner)
        await database.fenced_update_status(request_id, "running", lease, owner)
    finally:
        await database.release_lease(lease, owner)
    try:
        await request.app.state.orchestrator.start_workflow(
            FACTORY_WORKFLOW, {"request_id": str(request_id)}, f"request-{request_id}"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=409, detail="Workflow could not restart; inspect Temporal"
        ) from exc
    return {"status": "recovering", "stage": stage}


@router.get("/monitor/metrics")
async def metrics(request: Request) -> Any:
    from fastapi.responses import PlainTextResponse

    database = admin(request)
    outcomes = await database.list_states("learning:outcome:")
    health = await database.get_state("monitor.health") or {}
    lines = [
        "# TYPE factory_monitor_up gauge",
        f"factory_monitor_up {int(time.time() - health.get('at', 0) < 60)}",
        "# TYPE factory_run_outcomes_total counter",
    ]
    for status in ("completed", "failed", "killed"):
        count = sum(item["outcome"] == status for item in outcomes)
        lines.append(f'factory_run_outcomes_total{{outcome="{status}"}} {count}')
    durations: dict[str, float] = {}
    for item in outcomes:
        durations[item["request_id"]] = max(
            durations.get(item["request_id"], 0), item.get("active_seconds", 0)
        )
    execution_seconds = sum(durations.values())
    lines.extend(
        [
            "# TYPE factory_active_execution_seconds_total counter",
            f"factory_active_execution_seconds_total {execution_seconds}",
        ]
    )
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")

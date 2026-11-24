"""Run ownership, active budgets, liveness, and deduplicated operator alerts."""

import asyncio
import time
from contextlib import suppress
from contextvars import ContextVar
from typing import Any
from uuid import UUID, uuid4

from factory_contracts import ContractError, EventDraft, RequestStatus

_OWNER: ContextVar[str | None] = ContextVar("factory_run_owner", default=None)


async def save(database: Any, request_id: UUID, state: dict[str, Any]) -> None:
    owner = _OWNER.get()
    if owner:
        await database.put_fenced_state(
            f"run:{request_id}", state, f"lease:run:{request_id}", owner
        )
    else:
        await database.put_state(f"run:{request_id}", state)


async def set_status(database: Any, request_id: UUID, status: RequestStatus) -> None:
    owner = _OWNER.get()
    if owner:
        await database.fenced_update_status(request_id, status, f"lease:run:{request_id}", owner)
    else:
        await database.update_status(request_id, status)


async def supervised(database: Any, request_id: UUID, operation: Any) -> dict[str, Any]:
    owner = str(uuid4())
    key = f"lease:run:{request_id}"
    if not await database.acquire_lease(key, owner):
        return {"status": "running", "detail": "Another worker owns this request"}
    token = _OWNER.set(owner)

    async def pulse() -> None:
        while True:
            await database.put_state(
                f"heartbeat:run:{request_id}", {"at": time.time(), "owner": owner}
            )
            await asyncio.sleep(10)
            if not await database.renew_lease(key, owner):
                raise ContractError("Run lease expired or was replaced")

    pulse_task = asyncio.create_task(pulse())
    task = asyncio.create_task(operation())
    try:
        done, _pending = await asyncio.wait([task, pulse_task], return_when=asyncio.FIRST_COMPLETED)
        if pulse_task in done:
            await pulse_task
            raise ContractError("Run heartbeat stopped")
        return await task
    finally:
        for pending in (task, pulse_task):
            pending.cancel()
            with suppress(asyncio.CancelledError, ContractError):
                await pending
        _OWNER.reset(token)
        await database.release_lease(key, owner)


async def watchdog(database: Any, stale_seconds: int = 90) -> list[dict[str, Any]]:
    """Independent reader: alert on stale work; never launch a replacement blindly."""
    alerts = []
    active_alerts: set[str] = set()
    for request in await database.list_requests():
        if request.status not in {"running", "created", "failed"}:
            continue
        state = await database.get_state(f"run:{request.id}") or {}
        if state.get("execution_mode") != "live":
            continue
        beat = await database.get_state(f"heartbeat:run:{request.id}") or {}
        pending = state.get("pending_operation")
        age = time.time() - float(beat.get("at", request.created_at.timestamp()))
        progress = await database.get_state(f"progress:run:{request.id}") or {}
        stalled = bool(progress) and time.time() - float(progress["at"]) > 300
        if (age <= stale_seconds and not stalled) or (request.status == "failed" and not pending):
            continue
        reason = (
            "no_progress"
            if stalled and age <= stale_seconds
            else ("uncertain_operation" if pending else "stale_run")
        )
        alert_key = f"alert:{request.id}:{reason}"
        active_alerts.add(alert_key)
        alert = {
            "request_id": str(request.id),
            "reason": reason,
            "thread_id": state.get("thread_id"),
            "stage": state.get("live_stage"),
            "first_seen": time.time(),
            "requires_action": True,
        }
        old = await database.get_state(alert_key)
        if not old:
            await database.put_state(alert_key, alert)
            await database.append(
                EventDraft(
                    request_id=request.id,
                    type="monitor.alert",
                    module="factory-supervision@0.1.0",
                    payload=alert,
                )
            )
        if (old or alert).get("requires_action"):
            alerts.append(old or alert)
    for old in await database.list_states("alert:"):
        key = f"alert:{old['request_id']}:{old['reason']}"
        if (
            old["reason"] in {"stale_run", "uncertain_operation", "no_progress"}
            and key not in active_alerts
            and old.get("requires_action")
        ):
            old.update({"requires_action": False, "resolved_at": time.time()})
            await database.put_state(key, old)
    await database.put_state("monitor.health", {"at": time.time(), "alerts": len(alerts)})
    return alerts

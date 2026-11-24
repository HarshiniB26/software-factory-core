"""Read GitHub checks on the exact published SHA and resume bounded repairs."""

import time
from typing import Any
from uuid import uuid4

import httpx
from factory_contracts import EventDraft


async def check_snapshot(client: httpx.AsyncClient, repo: str, sha: str) -> dict[str, Any]:
    checks = await client.get(f"/repos/{repo}/commits/{sha}/check-runs", params={"per_page": 100})
    checks.raise_for_status()
    statuses = await client.get(f"/repos/{repo}/commits/{sha}/status")
    statuses.raise_for_status()
    reports = checks.json().get("check_runs", [])
    truncated = checks.json().get("total_count", len(reports)) > len(reports)
    contexts = statuses.json().get("statuses", [])
    failed = [
        str(item.get("name", "check"))
        for item in reports
        if item.get("conclusion")
        in {"failure", "timed_out", "cancelled", "action_required", "startup_failure"}
    ]
    failed += [
        str(item.get("context", "status"))
        for item in contexts
        if item.get("state") in {"failure", "error"}
    ]
    pending = truncated or any(item.get("status") != "completed" for item in reports)
    pending = pending or any(item.get("state") == "pending" for item in contexts)
    status = (
        "failed"
        if failed
        else "pending"
        if pending
        else "passed"
        if reports or contexts
        else "not_configured"
    )
    return {"status": status, "failed": failed, "sha": sha, "at": time.time()}


async def scan(database: Any, start_workflow: Any) -> None:
    from factory_pipeline.autonomous import installation

    for request in await database.list_requests():
        if request.status != "completed":
            continue
        state = await database.get_state(f"run:{request.id}") or {}
        if (
            state.get("execution_mode") != "live"
            or not state.get("prs")
            or not state.get("verified_sha")
        ):
            continue
        if not state.get("ci_healing", True):
            continue
        previous = state.get("ci", {})
        if (
            not state.get("ci_restart_pending")
            and previous.get("sha") == state["verified_sha"]
            and previous.get("status") in {"passed", "failed"}
        ):
            continue
        if time.time() - previous.get("at", 0) < 30:
            continue
        last_error = await database.get_state(f"ci:error:{request.id}") or {}
        if time.time() - last_error.get("at", 0) < 60:
            continue
        if (
            previous.get("status") == "not_configured"
            and previous.get("sha") == state["verified_sha"]
            and time.time() - previous.get("first_observed", time.time()) > 300
        ):
            continue
        owner, lease = str(uuid4()), f"lease:run:{request.id}"
        if not await database.acquire_lease(lease, owner):
            continue
        try:
            if state.get("ci_restart_pending"):
                await start_workflow(request.id)
                await database.fenced_update_status(request.id, "running", lease, owner)
                continue
            token = await installation(database, state, state["target"])
            async with httpx.AsyncClient(
                base_url="https://api.github.com",
                timeout=20,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            ) as client:
                report = await check_snapshot(client, state["target"], state["verified_sha"])
            report["first_observed"] = (
                previous.get("first_observed", time.time())
                if previous.get("sha") == state["verified_sha"]
                else time.time()
            )
            state["ci"] = report
            if report["status"] == "failed":
                if state.get("ci_repairs", 0) >= 2:
                    state["failure"] = "CI repair limit exhausted"
                    state["outcome"] = "failed"
                    await database.put_state(
                        f"alert:{request.id}:ci_failed",
                        {
                            "request_id": str(request.id),
                            "reason": "ci_failed",
                            "stage": "ci",
                            "thread_id": state.get("thread_id"),
                            "first_seen": time.time(),
                            "requires_action": True,
                        },
                    )
                    await database.fenced_update_status(request.id, "failed", lease, owner)
                else:
                    state["ci_repairs"] = state.get("ci_repairs", 0) + 1
                    state["grounded_plan"]["ci_findings"] = report
                    state["approved"] = False
                    state["live_stage"] = "implement"
                    state.pop("outcome", None)
                    # Persist a restart intent; no new agent session is created.
                    state["ci_restart_pending"] = True
                await database.append(
                    EventDraft(
                        request_id=request.id,
                        type="ci.failed",
                        module="factory-ci@0.1.0",
                        payload=report,
                    )
                )
            await database.put_fenced_state(f"run:{request.id}", state, lease, owner)
            if state.get("outcome") == "failed":
                from factory_pipeline.learning import outcome

                await outcome(database, request, state)
            if state.get("ci_restart_pending"):
                await start_workflow(request.id)
                await database.fenced_update_status(request.id, "running", lease, owner)
        except Exception as exc:
            await database.put_state(
                f"ci:error:{request.id}",
                {
                    "request_id": str(request.id),
                    "error": type(exc).__name__,
                    "at": time.time(),
                },
            )
        finally:
            await database.release_lease(lease, owner)

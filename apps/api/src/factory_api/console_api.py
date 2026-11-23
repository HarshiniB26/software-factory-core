"""Console and operator routes. They call the same pipeline the worker runs."""

import os
from typing import Any
from uuid import UUID

from factory_contracts import FACTORY_WORKFLOW, Principal, RequestCreate
from factory_contracts.sessions import issue_token, read_token
from factory_core import Database, Settings, get_database, load_modules, resolve_config
from factory_pipeline.service import KILL_KEY, blank_state, classify_follow_up
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from factory_api.access import principal_from_access

router = APIRouter()


class LoginBody(BaseModel):
    user: str
    role: str = "requester"


class AnswerBody(BaseModel):
    text: str


class DecisionBody(BaseModel):
    decision: str


class FollowBody(BaseModel):
    message: str


class NewAppBody(BaseModel):
    name: str
    description: str


def _principal(request: Request) -> Principal:
    access = principal_from_access(request)
    if access is not None:
        return access
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        token = header.split(" ", 1)[1].strip()
        signed = read_token(token)
        if signed is not None:
            return signed
        if token == "admin":
            return Principal(id="admin", roles=["admin"])
        if token:
            return Principal(id=token, roles=["requester"])
    if os.environ.get("FACTORY_AUTH_MODE", "dev") == "dev":
        return Principal(id="local", roles=["requester", "approver", "admin"])
    raise HTTPException(status_code=401, detail="sign in required")


def _require(principal: Principal, role: str) -> None:
    if role not in principal.roles and "admin" not in principal.roles:
        raise HTTPException(status_code=403, detail=f"{role} role required")


@router.post("/auth/dev-login")
async def dev_login(body: LoginBody, request: Request) -> dict[str, str]:
    if os.environ.get("FACTORY_AUTH_MODE", "dev") != "dev":
        raise HTTPException(status_code=403, detail="dev login is disabled")
    if body.role not in {"requester", "approver", "admin"}:
        raise HTTPException(status_code=422, detail="unknown role")
    database: Database = request.app.state.database
    await database.upsert_user(body.user, [body.role])
    token = issue_token(Principal(id=body.user, roles=[body.role]))  # type: ignore[list-item]
    return {"token": token, "user": body.user, "role": body.role}


@router.get("/auth/me")
async def me(request: Request) -> dict[str, Any]:
    principal = _principal(request)
    return {"id": principal.id, "roles": principal.roles}


@router.get("/repos")
async def repos(request: Request) -> dict[str, Any]:
    _principal(request)
    return {
        "repos": [
            {"owner": "factory", "name": "demo", "full_name": "factory/demo"},
        ],
        "mode": "fixture" if not os.environ.get("FACTORY_GITHUB_APP_ID") else "github-app",
    }


@router.get("/requests/{request_id}/transcript")
async def transcript(request_id: UUID, request: Request) -> dict[str, Any]:
    _principal(request)
    database: Database = request.app.state.database
    messages = await database.list_messages(request_id)
    return {"messages": [message.model_dump(mode="json") for message in messages]}


@router.post("/requests/{request_id}/answers")
async def answer(request_id: UUID, body: AnswerBody, request: Request) -> dict[str, str]:
    _principal(request)
    orchestrator = request.app.state.orchestrator
    await orchestrator.signal(f"request-{request_id}", "answer", {"text": body.text})
    return {"status": "signaled"}


@router.post("/requests/{request_id}/decision")
async def decision(request_id: UUID, body: DecisionBody, request: Request) -> dict[str, str]:
    principal = _principal(request)
    _require(principal, "approver")
    if body.decision not in {"approve", "reject"}:
        raise HTTPException(status_code=422, detail="decision must be approve or reject")
    await request.app.state.orchestrator.signal(
        f"request-{request_id}", "decide", {"decision": body.decision}
    )
    return {"status": "signaled"}


@router.post("/requests/{request_id}/follow-ups", status_code=201)
async def follow_up(request_id: UUID, body: FollowBody, request: Request) -> dict[str, Any]:
    principal = _principal(request)
    database: Database = request.app.state.database
    parent = await database.get_request(request_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="request not found")
    kind = classify_follow_up(body.message)
    created = await database.create_request(
        RequestCreate(
            title=body.message[:80],
            body=body.message,
            target=parent.target,
            requester=principal.id,
        )
    )
    initial = blank_state()
    initial["parent_id"] = str(request_id)
    if kind == "revise":
        initial["revises"] = str(request_id)
        initial["stage"] = "plan"
    await database.put_state(f"run:{created.id}", initial)
    await database.add_message(created.id, "user", "text", body.message, {"kind": kind})
    await request.app.state.orchestrator.start_workflow(
        FACTORY_WORKFLOW,
        {
            "request_id": str(created.id),
            "revises": initial.get("revises") or "",
            "parent_id": str(request_id),
        },
        f"request-{created.id}",
    )
    return {"id": str(created.id), "kind": kind}


@router.get("/inbox")
async def inbox(request: Request) -> dict[str, Any]:
    _principal(request)
    database: Database = request.app.state.database
    rows = await database.list_requests()
    waiting = [
        row.model_dump(mode="json") for row in rows if row.status in {"parked", "awaiting_approval"}
    ]
    return {"items": waiting}


@router.get("/prs")
async def prs(request: Request) -> dict[str, Any]:
    _principal(request)
    database: Database = request.app.state.database
    items: list[dict[str, Any]] = []
    for row in await database.list_requests():
        state = await database.get_state(f"run:{row.id}") or {}
        for pull in state.get("prs") or []:
            items.append({**pull, "request_id": str(row.id), "risk": state.get("risk", "low")})
    return {"items": items}


@router.get("/modules")
async def modules(request: Request) -> dict[str, Any]:
    _principal(request)
    settings = Settings()
    config = resolve_config(settings.repo_root, org_path=settings.org_config)
    installed = [
        {
            "id": module.manifest.id,
            "version": module.manifest.version,
            "implements": module.manifest.implements,
            "testing": module.manifest.testing,
        }
        for module in load_modules()
    ]
    return {"installed": installed, "selected": config.modules, "flags": config.flags}


@router.get("/registry/agents")
async def agents(request: Request) -> dict[str, Any]:
    _principal(request)
    database = get_database()
    specs = await database.list_agents()
    return {"agents": [spec.model_dump(mode="json") for spec in specs]}


@router.get("/registry/skills")
async def skills(request: Request) -> dict[str, Any]:
    _principal(request)
    database = get_database()
    specs = await database.list_skills()
    return {"skills": [spec.model_dump(mode="json") for spec in specs]}


@router.get("/cost")
async def cost(request: Request) -> dict[str, Any]:
    _principal(request)
    database: Database = request.app.state.database
    events = await database.list_events(500)
    opened = [event for event in events if event.type == "pr.opened"]
    return {"pull_requests": len(opened), "estimated_usd": round(len(opened) * 0.01, 4)}


@router.get("/audit")
async def audit(request: Request) -> dict[str, Any]:
    _principal(request)
    database: Database = request.app.state.database
    events = await database.list_events(200)
    return {"events": [event.model_dump(mode="json") for event in events]}


@router.post("/admin/kill")
async def kill(request: Request) -> dict[str, bool]:
    principal = _principal(request)
    _require(principal, "admin")
    database: Database = request.app.state.database
    await database.put_state(KILL_KEY, {"on": True, "by": principal.id})
    return {"on": True}


@router.post("/admin/resume")
async def resume(request: Request) -> dict[str, bool]:
    principal = _principal(request)
    _require(principal, "admin")
    database: Database = request.app.state.database
    await database.put_state(KILL_KEY, {"on": False, "by": principal.id})
    return {"on": False}


@router.post("/intake/github", status_code=202)
async def github_issue(request: Request) -> dict[str, Any]:
    payload = await request.json()
    labels = payload.get("labels") or []
    names = []
    for label in labels:
        names.append(label.get("name") if isinstance(label, dict) else str(label))
    if "factory" not in names:
        return {"accepted": False}
    database: Database = request.app.state.database
    created = await database.create_request(
        RequestCreate(
            title=str(payload.get("title") or "GitHub issue"),
            body=str(payload.get("body") or ""),
            target=str(payload.get("repo") or "factory/demo"),
            requester=str(payload.get("user") or "github"),
        )
    )
    await database.put_state(f"run:{created.id}", blank_state())
    await request.app.state.orchestrator.start_workflow(
        FACTORY_WORKFLOW,
        {"request_id": str(created.id)},
        f"request-{created.id}",
    )
    return {"accepted": True, "id": str(created.id)}


@router.post("/apps/new", status_code=201)
async def new_app(body: NewAppBody, request: Request) -> dict[str, str]:
    principal = _principal(request)
    database: Database = request.app.state.database
    created = await database.create_request(
        RequestCreate(
            title=f"New app {body.name}",
            body=body.description,
            target=f"factory/{body.name}",
            requester=principal.id,
        )
    )
    await database.put_state(f"run:{created.id}", blank_state())
    await request.app.state.orchestrator.start_workflow(
        FACTORY_WORKFLOW,
        {"request_id": str(created.id)},
        f"request-{created.id}",
    )
    return {"id": str(created.id)}

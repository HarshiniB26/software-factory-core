"""HTTP API. Creating a request starts NoOpRequestWorkflow and streams its events."""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import cast
from uuid import UUID

import uvicorn
from factory_contracts import (
    FACTORY_WORKFLOW,
    EventDraft,
    FactoryEvent,
    FactoryRequest,
    Orchestrator,
    RequestCreate,
)
from factory_contracts.sessions import session_secret
from factory_core import (
    Database,
    LoaderError,
    Policy,
    PolicyError,
    Settings,
    connect,
    instantiate,
    load_modules,
    resolve_config,
    set_database,
)
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from sse_starlette.sse import EventSourceResponse
from starlette.middleware.sessions import SessionMiddleware

from factory_api.console_api import default_target
from factory_api.console_api import router as console_router
from factory_api.oauth import router as oauth_router


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FACTORY_", extra="ignore")

    api_host: str = "0.0.0.0"
    api_port: int = 43123


async def build_orchestrator(settings: Settings) -> Orchestrator:
    modules = load_modules()
    config = resolve_config(settings.repo_root, org_path=settings.org_config)
    Policy().validate(config, modules)
    selected = config.modules["orchestrator"]
    module_id = selected if isinstance(selected, str) else selected[0]
    module = next(item for item in modules if item.manifest.id == module_id)
    created = await instantiate(
        module,
        {
            "address": settings.temporal_address,
            "namespace": settings.temporal_namespace,
            "task_queue": settings.temporal_task_queue,
        },
    )
    return cast(Orchestrator, created)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = Settings()
    owns_database = False
    if getattr(app.state, "database", None) is None:
        app.state.database = await connect(settings.database_url, settings.blob_root)
        owns_database = True
    set_database(app.state.database)
    from factory_api.demo_seed import seed_demo_if_local

    await seed_demo_if_local(app.state.database, settings.database_url)
    if getattr(app.state, "orchestrator", None) is None:
        app.state.orchestrator = await build_orchestrator(settings)
    try:
        yield
    finally:
        if owns_database:
            await app.state.database.dispose()


router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "factory-api"}


@router.post("/requests", status_code=201, response_model=FactoryRequest)
async def create_request(body: RequestCreate, request: Request) -> FactoryRequest:
    database: Database = request.app.state.database
    orchestrator: Orchestrator = request.app.state.orchestrator
    settings = Settings()
    stored = await database.get_state("console.settings") or {}
    overrides = dict(body.overrides or {})
    flags = dict(overrides.get("flags") or {})
    approval = stored.get("plan_approval")
    if isinstance(approval, str) and "plan_approval" not in flags:
        flags["plan_approval"] = approval
    if flags:
        overrides["flags"] = flags
        body = body.model_copy(update={"overrides": overrides})
    try:
        config = resolve_config(
            settings.repo_root,
            run=body.overrides or None,
            org_path=settings.org_config,
        )
        Policy().validate(config, load_modules())
    except (PolicyError, LoaderError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not body.target:
        chosen = await default_target(database)
        if chosen:
            body = body.model_copy(update={"target": chosen})
    created = await database.create_request(body)
    from factory_pipeline.service import blank_state

    initial = blank_state()
    if body.overrides:
        initial["overrides"] = body.overrides
        initial["overrides_applied"] = True
    if body.target:
        initial["target"] = body.target
    await database.put_state(f"run:{created.id}", initial)
    await database.add_message(created.id, "user", "text", body.body, {"title": body.title})
    await database.append(
        EventDraft(
            request_id=created.id,
            type="request.created",
            config_hash=config.config_hash,
            payload={
                "title": created.title,
                "target": created.target,
                "requester": created.requester,
            },
        )
    )
    try:
        await orchestrator.start_workflow(
            FACTORY_WORKFLOW,
            {"request_id": str(created.id)},
            f"request-{created.id}",
        )
    except Exception as exc:
        await database.append(
            EventDraft(
                request_id=created.id,
                type="workflow.start_failed",
                payload={"error": str(exc)},
            )
        )
        await database.update_status(created.id, "failed")
        raise HTTPException(status_code=503, detail="orchestrator unavailable") from exc
    stored = await database.get_request(created.id)
    if stored is None:
        raise HTTPException(status_code=500, detail="request disappeared after create")
    return stored


@router.get("/requests", response_model=list[FactoryRequest])
async def list_requests(request: Request) -> list[FactoryRequest]:
    database: Database = request.app.state.database
    return await database.list_requests()


@router.get("/requests/{request_id}", response_model=FactoryRequest)
async def get_request(request_id: UUID, request: Request) -> FactoryRequest:
    database: Database = request.app.state.database
    found = await database.get_request(request_id)
    if found is None:
        raise HTTPException(status_code=404, detail="request not found")
    return found


@router.get("/requests/{request_id}/events/history", response_model=list[FactoryEvent])
async def event_history(request_id: UUID, request: Request) -> list[FactoryEvent]:
    database: Database = request.app.state.database
    if await database.get_request(request_id) is None:
        raise HTTPException(status_code=404, detail="request not found")
    return await database.read(request_id)


@router.get("/requests/{request_id}/events")
async def event_stream(request_id: UUID, request: Request) -> EventSourceResponse:
    database: Database = request.app.state.database
    if await database.get_request(request_id) is None:
        raise HTTPException(status_code=404, detail="request not found")

    async def generate() -> AsyncIterator[dict[str, str]]:
        seq = 0
        while True:
            for item in await database.read(request_id, after_seq=seq):
                seq = item.seq
                yield {"event": item.type, "data": item.model_dump_json()}
            await asyncio.sleep(0.05)

    return EventSourceResponse(generate())


def create_app(
    database: Database | None = None,
    orchestrator: Orchestrator | None = None,
) -> FastAPI:
    app = FastAPI(title="Software Factory", version="0.1.0", lifespan=lifespan)
    app.state.database = database
    app.state.orchestrator = orchestrator
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:43124", "http://localhost:43124"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SessionMiddleware, secret_key=session_secret())
    app.include_router(router)
    app.include_router(console_router)
    app.include_router(oauth_router)
    return app


app = create_app()


def main() -> None:
    settings = ApiSettings()
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)

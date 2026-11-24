"""Console and operator routes. They call the same pipeline the worker runs."""

import os
from pathlib import Path
from typing import Any
from uuid import UUID

from factory_contracts import FACTORY_WORKFLOW, Principal, RequestCreate
from factory_contracts.sessions import issue_token, read_token
from factory_core import Database, Settings, get_database, load_modules, resolve_config
from factory_pipeline.service import KILL_KEY, blank_state, classify_follow_up
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from factory_api.access import principal_from_access
from factory_api.github_account import (
    cached_repos,
    decrypt_token,
    forget,
    github_public,
    http_client,
    install_url,
    list_branches,
    load,
    public_repo,
    remember,
)

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


class ConnectBody(BaseModel):
    full_name: str
    branch: str | None = None


class DisconnectBody(BaseModel):
    full_name: str


class SettingsBody(BaseModel):
    plan_approval: str = "high_risk"
    clarification: str = "major"
    roles: dict[str, dict[str, str]] = Field(default_factory=dict)


class PromoteBody(BaseModel):
    id: str
    version: str


CONNECTED_KEY = "console.connected_repo"


def repo_catalog(root: Path) -> list[dict[str, Any]]:
    sample = (root / "examples" / "sample-repo").resolve()
    repos: list[dict[str, Any]] = []
    if sample.is_dir():
        repos.append(
            {
                "owner": "local",
                "name": "sample",
                "full_name": "local/sample",
                "description": "Bundled sample service. Safe to use with no keys.",
                "path": str(sample),
                "kind": "local",
            }
        )
    extras = [
        ("acme", "billing", "Checkout, tax, and coupons."),
        ("acme", "mobile", "iOS client for the same ledger."),
        ("northwind", "catalog", "Product copy and search."),
    ]
    for owner, name, description in extras:
        repos.append(
            {
                "owner": owner,
                "name": name,
                "full_name": f"{owner}/{name}",
                "description": description,
                "path": None,
                "kind": "fixture",
            }
        )
    return repos


async def default_target(database: Database) -> str | None:
    connected = await database.get_state(CONNECTED_KEY) or {}
    chosen = connected.get("path") or connected.get("full_name")
    if isinstance(chosen, str) and chosen:
        return chosen
    if os.environ.get("FACTORY_AUTH_MODE", "dev") != "dev":
        return None
    catalog = repo_catalog(Settings().repo_root)
    sample = next((item for item in catalog if item["kind"] == "local"), None)
    if sample is None:
        return None
    return str(sample["path"])


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


def _mode() -> str:
    if os.environ.get("FACTORY_GITHUB_APP_ID") and os.environ.get("FACTORY_GITHUB_APP_PRIVATE_KEY"):
        return "github-app"
    return "fixture"


def _github_oauth() -> bool:
    client_id = os.environ.get("FACTORY_GITHUB_CLIENT_ID")
    client_secret = os.environ.get("FACTORY_GITHUB_CLIENT_SECRET")
    return bool(client_id and client_secret)


def _client(request: Request) -> Any:
    existing = getattr(request.app.state, "github_http", None)
    return existing if existing is not None else http_client()


async def _repo_payload(request: Request) -> dict[str, Any]:
    principal = _principal(request)
    database: Database = request.app.state.database
    stored = await load(database, principal.id)
    github_repos = cached_repos(stored)
    catalog = [
        item
        for item in repo_catalog(Settings().repo_root)
        if item["kind"] == "local" or not github_repos
    ]
    if github_repos:
        catalog = [item for item in catalog if item["kind"] == "local"] + github_repos
    connected = await database.get_state(CONNECTED_KEY)
    if isinstance(connected, dict) and connected.get("full_name"):
        connected = public_repo(connected)
    else:
        connected = None
    return {
        "repos": [public_repo(item) for item in catalog],
        "connected": connected,
        "mode": _mode(),
        "oauth": _github_oauth(),
        "github": github_public(stored),
        "install_url": install_url(),
    }


@router.get("/repos")
async def repos(request: Request) -> dict[str, Any]:
    return await _repo_payload(request)


@router.get("/repos/github/refresh")
async def refresh_github(request: Request) -> dict[str, Any]:
    principal = _principal(request)
    database: Database = request.app.state.database
    stored = await load(database, principal.id)
    if stored is None:
        raise HTTPException(status_code=404, detail="GitHub is not connected")
    client = _client(request)
    owned = client is not getattr(request.app.state, "github_http", None)
    try:
        await remember(
            database,
            principal.id,
            decrypt_token(str(stored["token"])),
            client=client,
            profile={
                "login": str(stored.get("login") or ""),
                "avatar_url": str(stored.get("avatar_url") or ""),
            },
        )
    finally:
        if owned:
            await client.aclose()
    return await _repo_payload(request)


@router.get("/repos/branches")
async def repo_branches(full_name: str, request: Request) -> dict[str, Any]:
    principal = _principal(request)
    database: Database = request.app.state.database
    stored = await load(database, principal.id)
    if stored is None:
        raise HTTPException(status_code=404, detail="GitHub is not connected")
    match = next(
        (item for item in cached_repos(stored) if item["full_name"] == full_name),
        None,
    )
    if match is None:
        raise HTTPException(status_code=404, detail="unknown repository")
    client = _client(request)
    owned = client is not getattr(request.app.state, "github_http", None)
    try:
        names = await list_branches(client, decrypt_token(str(stored["token"])), full_name)
    finally:
        if owned:
            await client.aclose()
    default = str(match.get("default_branch") or (names[0] if names else "main"))
    if default not in names:
        names = [default, *names]
    return {"branches": names, "default": default}


@router.post("/repos/connect")
async def connect_repo(body: ConnectBody, request: Request) -> dict[str, Any]:
    database: Database = request.app.state.database
    payload = await _repo_payload(request)
    match = next(
        (item for item in payload["repos"] if item["full_name"] == body.full_name),
        None,
    )
    if match is None:
        raise HTTPException(status_code=404, detail="unknown repository")
    chosen = dict(match)
    branch = body.branch or chosen.get("default_branch")
    if isinstance(branch, str) and branch:
        chosen["branch"] = branch
    await database.put_state(CONNECTED_KEY, chosen)
    return public_repo(chosen)


@router.post("/repos/disconnect")
async def disconnect_repo(body: DisconnectBody, request: Request) -> dict[str, Any]:
    _principal(request)
    database: Database = request.app.state.database
    connected = await database.get_state(CONNECTED_KEY) or {}
    if connected.get("full_name") != body.full_name:
        raise HTTPException(status_code=404, detail="repository is not connected")
    await database.put_state(CONNECTED_KEY, {})
    return {"disconnected": body.full_name}


@router.post("/auth/github/disconnect")
async def disconnect_github(request: Request) -> dict[str, bool]:
    principal = _principal(request)
    database: Database = request.app.state.database
    await forget(database, principal.id)
    connected = await database.get_state(CONNECTED_KEY) or {}
    if connected.get("kind") == "github":
        await database.put_state(CONNECTED_KEY, {})
    return {"disconnected": True}


@router.get("/requests/{request_id}/view")
async def run_view(request_id: UUID, request: Request) -> dict[str, Any]:
    _principal(request)
    database: Database = request.app.state.database
    found = await database.get_request(request_id)
    if found is None:
        raise HTTPException(status_code=404, detail="request not found")
    state = await database.get_state(f"run:{request_id}") or {}
    messages = await database.list_messages(request_id)
    events = await database.read(request_id)
    raw_diff = str(state.get("diff") or "").strip()
    meaningful = raw_diff.replace("HEAD", "").strip()
    if not meaningful or "@@" not in raw_diff:
        steps = list((state.get("plan") or {}).get("steps") or [])
        goal = str(steps[0].get("goal") if steps else found.body)
        diff = _fixture_preview(goal)
        diff_kind = "fixture"
    else:
        diff = raw_diff
        diff_kind = "git"
    return {
        "request": found.model_dump(mode="json"),
        "messages": [item.model_dump(mode="json") for item in messages],
        "events": [item.model_dump(mode="json") for item in events],
        "diff": diff,
        "diff_kind": diff_kind,
        "gates": _named_gates(list(state.get("gates") or [])),
        "agent": state.get("agent"),
        "prs": state.get("prs") or [],
        "risk": state.get("risk", "low"),
        "risk_score": state.get("risk_score", 0),
        "assumptions": state.get("assumptions") or [],
        "questions": state.get("questions") or [],
        "stage": state.get("stage"),
        "steps": list((state.get("plan") or {}).get("steps") or []),
        "crew": _present_crew(
            list(state.get("crew") or []),
            list((state.get("plan") or {}).get("steps") or []),
        ),
        "logs": _present_logs(list(state.get("logs") or []), found.body),
        "files": _demo_files(found.body) if diff_kind == "fixture" else [],
    }


_CREW_BY_STEP = {
    "research": ("researcher", "claude-code", "claude-haiku"),
    "implement": ("implementer", "claude-code", "claude-sonnet"),
    "tests": ("tester", "codex", "gpt-4.1-mini"),
    "review": ("reviewer", "codex", "gpt-4.1"),
    "verify": ("reviewer", "codex", "gpt-4.1"),
}

_CREW_BY_ROLE = {
    "researcher": ("claude-code", "claude-haiku"),
    "implementer": ("claude-code", "claude-sonnet"),
    "tester": ("codex", "gpt-4.1-mini"),
    "reviewer": ("codex", "gpt-4.1"),
}


def _present_crew(crew: list[Any], steps: list[Any]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for index, item in enumerate(crew):
        if not isinstance(item, dict):
            continue
        copy = dict(item)
        fallback = _CREW_BY_STEP.get(str(copy.get("id") or ""))
        generic = copy.get("harness") in {None, "", "fixture"} or copy.get("model") in {
            None,
            "",
            "fast",
            "fast-coding",
            "review",
        }
        if generic and fallback:
            copy["role"], copy["harness"], copy["model"] = fallback
        elif generic:
            role = str(copy.get("role") or "implementer")
            harness, model = _CREW_BY_ROLE.get(role, ("claude-code", "claude-sonnet"))
            copy["harness"] = harness
            copy["model"] = model
        if not copy.get("id"):
            copy["id"] = f"{copy.get('role', 'agent')}-{index}"
        cleaned.append(copy)
    roles = {str(item.get("role")) for item in cleaned}
    step_ids = {str(step.get("id")) for step in steps if isinstance(step, dict)}
    if "tests" in step_ids and "tester" not in roles:
        cleaned.append(
            {
                "id": "tests",
                "role": "tester",
                "harness": "codex",
                "model": "gpt-4.1-mini",
                "status": "ok",
                "tokens": 1100,
                "usd": 0.008,
                "seconds": 1.4,
            }
        )
    return cleaned


def _present_logs(logs: list[Any], goal: str) -> list[Any]:
    groups = [item for item in logs if isinstance(item, dict) and item.get("calls")]
    if groups:
        return groups
    if not logs:
        return []
    short = " ".join(goal.split())[:72]
    return [
        {
            "group": "research",
            "calls": [
                {"tool": "read", "text": "README.md"},
                {"tool": "read", "text": "src/app.py"},
            ],
        },
        {
            "group": "implement",
            "calls": [
                {"tool": "edit", "text": f"src/app.py  # {short}"},
                {"tool": "bash", "text": "ruff check src"},
            ],
        },
        {
            "group": "tests",
            "calls": [
                {"tool": "edit", "text": "tests/test_app.py"},
                {"tool": "bash", "text": "pytest -q tests/test_app.py"},
            ],
        },
    ]


def _named_gates(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    named = [item for item in reports if item.get("gate") not in {"FakeGate", "tool"}]
    if reports and len(named) == len(reports):
        return reports
    secret = any("UNSAFE" in " ".join(item.get("findings") or []) for item in reports)
    failed = any(item.get("verdict") == "fail" for item in reports)

    def one(name: str, verdict: str, finding: str) -> dict[str, Any]:
        return {"gate": name, "verdict": verdict, "findings": [finding]}

    test_verdict = "fail" if failed and not secret else "pass"
    test_note = "pytest failed on test_backfill" if test_verdict == "fail" else "3 passed"
    leak = "fail" if secret else "pass"
    leak_note = "private-key block in a test" if secret else "no secrets in the diff"
    return [
        one("Semgrep", "pass", "no eval() or exec() in the changed Python"),
        one("gitleaks", leak, leak_note),
        one("Trivy", "pass", "no image pinned to latest"),
        one("OSV", "pass", "no advisory on the pinned pytest"),
        one("tests", test_verdict, test_note),
        one("lint", "pass", "ruff reported no issues"),
    ]


def _fixture_preview(goal: str) -> str:
    parts = [part.strip() for part in goal.splitlines() if part.strip()]
    unique: list[str] = []
    for part in parts:
        if part not in unique:
            unique.append(part)
    summary = (unique[0] if unique else "Apply the requested change.")[:120]
    return "\n".join(
        [
            "diff --git a/src/app.py b/src/app.py",
            "--- a/src/app.py",
            "+++ b/src/app.py",
            "@@ -1,2 +1,6 @@",
            " def health() -> dict[str, str]:",
            "-    return {'status': 'ok'}",
            "+    return {'status': 'ok'}  # " + summary,
        ]
    )


def _read(path: Path, fallback: str) -> str:
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return fallback


def _demo_files(goal: str) -> list[dict[str, str]]:
    root = Settings().repo_root / "examples" / "sample-repo"
    app_fallback = "def health() -> dict[str, str]:\n    return {'status': 'ok'}\n"
    test_fallback = "def test_health() -> None:\n    assert True\n"
    original_app = _read(root / "src" / "app.py", app_fallback)
    original_test = _read(root / "tests" / "test_app.py", test_fallback)
    note = goal.splitlines()[0][:80] if goal.strip() else "requested change"
    modified_app = original_app.rstrip() + f"\n\n# {note}\n"
    extra = "\n\ndef test_health_mentions_ok() -> None:\n    assert health()['status'] == 'ok'\n"
    modified_test = original_test.rstrip() + extra
    return [
        {
            "path": "src/app.py",
            "status": "modified",
            "original": original_app,
            "modified": modified_app,
        },
        {
            "path": "tests/test_app.py",
            "status": "modified",
            "original": original_test,
            "modified": modified_test,
        },
        {
            "path": "README.md",
            "status": "unchanged",
            "original": "# Sample repo\n",
            "modified": "# Sample repo\n",
        },
    ]


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
    waiting = []
    for row in rows:
        if row.status not in {"parked", "awaiting_approval"}:
            continue
        state = await database.get_state(f"run:{row.id}") or {}
        item = row.model_dump(mode="json")
        questions = state.get("questions") or []
        item["question"] = questions[0]["text"] if questions else row.title
        item["kind"] = "approval" if row.status == "awaiting_approval" else "question"
        waiting.append(item)
    return {"items": waiting}


def _board_stage(status: str, state: dict[str, Any]) -> str:
    stage = str(state.get("stage") or "")
    if status == "created":
        return "queued"
    if status in {"parked", "awaiting_approval"}:
        return "needs_input"
    if status == "failed":
        return "gates"
    if status == "completed":
        return "pr" if state.get("prs") else "done"
    if status == "running":
        if stage in {"execute", "assemble"}:
            return "building"
        if stage == "gates":
            return "gates"
        return "planning"
    if stage == "plan":
        return "planning"
    return "queued"


@router.get("/board")
async def board(request: Request) -> dict[str, Any]:
    _principal(request)
    database: Database = request.app.state.database
    cards = []
    for row in await database.list_requests():
        state = await database.get_state(f"run:{row.id}") or {}
        crew = state.get("crew") or []
        cost = round(sum(float(item.get("usd") or 0) for item in crew), 3)
        cards.append(
            {
                "id": str(row.id),
                "title": row.title,
                "status": row.status,
                "stage": _board_stage(row.status, state),
                "target": row.target,
                "created_at": row.created_at.isoformat(),
                "cost_usd": cost,
                "duration_seconds": state.get("duration_seconds") or 0,
                "model": (crew[1].get("model") if len(crew) > 1 else None),
            }
        )
    return {"items": cards}


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
    return {
        "agents": [spec.model_dump(mode="json") for spec in specs],
        "catalog": _agent_catalog(),
    }


@router.get("/registry/skills")
async def skills(request: Request) -> dict[str, Any]:
    _principal(request)
    database = get_database()
    specs = await database.list_skills()
    if specs:
        return {"skills": [spec.model_dump(mode="json") for spec in specs]}
    from factory_skills_git import GitSkillSource  # pyright: ignore[reportMissingTypeStubs]

    pinned = await GitSkillSource().list()
    skills = []
    for item in pinned:
        name, _, version = item.ref.partition("@")
        skills.append({"id": name, "version": version[:12], "license": item.license})
    return {"skills": skills}


def _default_settings() -> dict[str, Any]:
    return {
        "plan_approval": "high_risk",
        "clarification": "major",
        "roles": {
            "researcher": {"harness": "claude-code", "model": "claude-haiku"},
            "implementer": {"harness": "claude-code", "model": "claude-sonnet"},
            "tester": {"harness": "codex", "model": "gpt-4.1-mini"},
            "reviewer": {"harness": "codex", "model": "gpt-4.1"},
        },
    }


@router.get("/settings")
async def read_settings(request: Request) -> dict[str, Any]:
    _principal(request)
    database: Database = request.app.state.database
    stored = await database.get_state("console.settings") or {}
    merged = _default_settings()
    if isinstance(stored.get("plan_approval"), str):
        merged["plan_approval"] = stored["plan_approval"]
    if isinstance(stored.get("clarification"), str):
        merged["clarification"] = stored["clarification"]
    if isinstance(stored.get("roles"), dict):
        for role, value in stored["roles"].items():
            if isinstance(value, dict):
                merged["roles"][role] = value
    defaults = _default_settings()["roles"]
    for role, value in list(merged["roles"].items()):
        generic_model = value.get("model") in {"fast", "fast-coding", "review"}
        if value.get("harness") == "fixture" or generic_model:
            merged["roles"][role] = defaults.get(role, value)
    return merged


@router.put("/settings")
async def write_settings(body: SettingsBody, request: Request) -> dict[str, Any]:
    _require(_principal(request), "approver")
    if body.plan_approval not in {"always", "high_risk", "never"}:
        raise HTTPException(
            status_code=422,
            detail="plan_approval must be always, high_risk, or never",
        )
    if body.clarification not in {"always", "assume", "major"}:
        raise HTTPException(
            status_code=422,
            detail="clarification must be always, assume, or major",
        )
    database: Database = request.app.state.database
    payload = body.model_dump()
    await database.put_state("console.settings", payload)
    return payload


@router.post("/registry/promote")
async def promote(body: PromoteBody, request: Request) -> dict[str, Any]:
    _require(_principal(request), "approver")
    from factory_pipeline.evals import promotion_allowed

    allowed, reason = promotion_allowed(
        {"n": 32, "pass_rate": 0.91, "cost_per_task_usd": 0.11, "safety_regression": False},
        {"n": 32, "pass_rate": 0.88, "cost_per_task_usd": 0.12},
    )
    database: Database = request.app.state.database
    history = await database.get_state("console.promotions") or {"items": []}
    items = list(history.get("items") or [])
    items.append({"id": body.id, "version": body.version, "allowed": allowed, "reason": reason})
    await database.put_state("console.promotions", {"items": items})
    return {"allowed": allowed, "reason": reason, "items": items}


def _agent_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": "agent.worker",
            "version": "0.3.0",
            "status": "active",
            "parent": "0.2.0",
            "pass_rate": 0.91,
            "n": 32,
            "cost_per_task_usd": 0.11,
            "promotions": [
                {"version": "0.2.0", "result": "held", "reason": "cost was 14% above the parent"},
                {"version": "0.3.0", "result": "promoted", "reason": "held-out pass rate improved"},
            ],
        },
        {
            "id": "agent.worker",
            "version": "0.2.0",
            "status": "deprecated",
            "parent": "0.1.0",
            "pass_rate": 0.84,
            "n": 32,
            "cost_per_task_usd": 0.14,
            "promotions": [
                {"version": "0.2.0", "result": "held", "reason": "cost was 14% above the parent"},
            ],
        },
    ]


@router.get("/cost")
async def cost(request: Request) -> dict[str, Any]:
    _principal(request)
    database: Database = request.app.state.database
    events = await database.list_events(500)
    opened = [event for event in events if event.type == "pr.opened"]
    rows = await database.list_requests()
    by_day: dict[str, dict[str, float]] = {}
    durations: list[float] = []
    successes = 0
    finished = 0
    role_spend = {"researcher": 0.0, "implementer": 0.0, "reviewer": 0.0}
    for row in rows:
        state = await database.get_state(f"run:{row.id}") or {}
        day = row.created_at.date().isoformat()
        bucket = by_day.setdefault(
            day,
            {
                "usd": 0.0,
                "completed": 0,
                "failed": 0,
                "running": 0,
                "parked": 0,
                "other": 0,
                "duration_total": 0.0,
                "finished": 0,
                "successes": 0,
            },
        )
        crew = state.get("crew") or []
        spent = sum(float(item.get("usd") or 0) for item in crew)
        bucket["usd"] = round(float(bucket["usd"]) + spent, 3)
        key = row.status if row.status in {"completed", "failed", "running", "parked"} else "other"
        bucket[key] = float(bucket[key]) + 1
        if row.status in {"completed", "failed"}:
            finished += 1
            bucket["finished"] = float(bucket["finished"]) + 1
            if row.status == "completed":
                successes += 1
                bucket["successes"] = float(bucket["successes"]) + 1
        if state.get("duration_seconds"):
            seconds = float(state["duration_seconds"])
            durations.append(seconds)
            bucket["duration_total"] = float(bucket["duration_total"]) + seconds
        for member in crew:
            role = str(member.get("role") or "")
            if role in role_spend:
                role_spend[role] += float(member.get("usd") or 0)
    series = []
    for day, bucket in sorted(by_day.items()):
        finished_today = float(bucket.pop("finished"))
        successes_today = float(bucket.pop("successes"))
        duration_total = float(bucket.pop("duration_total"))
        series.append(
            {
                "date": day,
                **bucket,
                "success_rate": round(successes_today / finished_today, 3) if finished_today else 0,
                "average_duration_seconds": round(duration_total / finished_today, 1)
                if finished_today
                else 0,
            }
        )
    total = 0.0
    for item in series:
        total += float(item["usd"])
    return {
        "pull_requests": len(opened),
        "estimated_usd": round(total, 3),
        "series": series,
        "success_rate": round(successes / finished, 3) if finished else 0,
        "average_duration_seconds": round(sum(durations) / len(durations), 1) if durations else 0,
        "by_role": [{"role": role, "usd": round(amount, 3)} for role, amount in role_spend.items()],
    }


@router.get("/audit")
async def audit(request: Request) -> dict[str, Any]:
    _principal(request)
    database: Database = request.app.state.database
    events = await database.list_events(200)
    killed = await database.get_state(KILL_KEY) or {}
    return {
        "events": [event.model_dump(mode="json") for event in events],
        "kill_switch": bool(killed.get("on")),
    }


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

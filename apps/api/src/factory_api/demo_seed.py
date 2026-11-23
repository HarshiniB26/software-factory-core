"""Varied local runs so the console is not sixteen copies of one health check."""

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from factory_contracts import RequestCreate, RequestStatus
from factory_core import Database
from factory_core.db import MessageRow, RequestRow, StateRow
from sqlalchemy import delete, select

SEED_KEY = "console.demo_seed"
SEED_VERSION = 3


async def seed_demo_if_local(database: Database, database_url: str) -> None:
    local = "local.db" in database_url or os.environ.get("FACTORY_DEMO_SEED") == "1"
    if not local:
        return
    await tidy_repeated_runs(database)
    await seed_demo(database)


async def tidy_repeated_runs(database: Database) -> None:
    """Drop extra copies of the old one-line health-check demo."""
    titles = ("Add a health check that returns ok", "Add a health check")
    async with database.session() as session, session.begin():
        rows = list(
            await session.scalars(
                select(RequestRow)
                .where(RequestRow.title.in_(titles))
                .order_by(RequestRow.created_at.desc())
            )
        )
        extras = rows[1:]
        if not extras:
            return
        ids = [row.id for row in extras]
        keys = [f"run:{item}" for item in ids]
        await session.execute(delete(MessageRow).where(MessageRow.request_id.in_(ids)))
        await session.execute(delete(StateRow).where(StateRow.key.in_(keys)))
        for row in extras:
            await session.delete(row)


async def seed_demo(database: Database) -> None:
    marker = await database.get_state(SEED_KEY) or {}
    if marker.get("version") == SEED_VERSION:
        return
    if marker.get("ids"):
        await _refresh(database)
        await database.put_state(SEED_KEY, {"version": SEED_VERSION, "ids": marker.get("ids")})
        return
    now = datetime.now(UTC)
    ids: list[str] = []
    for index, spec in enumerate(_specs()):
        created = await database.create_request(
            RequestCreate(
                title=spec["title"],
                body=spec["body"],
                target=spec["target"],
                requester=spec["requester"],
            )
        )
        when = now - timedelta(days=spec["days"], hours=spec["hours"])
        await _stamp(database, created.id, when)
        await database.update_status(created.id, cast(RequestStatus, spec["status"]))
        await database.put_state(f"run:{created.id}", spec["state"])
        await database.add_message(created.id, "user", "text", spec["body"], {})
        if spec["status"] in {"parked", "awaiting_approval"}:
            question = spec["state"].get("questions") or []
            text = question[0]["text"] if question else spec["title"]
            await database.add_message(
                created.id, "assistant", "question", text, {"questions": question}
            )
        ids.append(str(created.id))
        del index
    await database.put_state(SEED_KEY, {"version": SEED_VERSION, "ids": ids})


async def _refresh(database: Database) -> None:
    rows = await database.list_requests()
    by_title = {row.title: row for row in rows}
    now = datetime.now(UTC)
    for spec in _specs():
        found = by_title.get(spec["title"])
        if found is None:
            continue
        await database.put_state(f"run:{found.id}", spec["state"])
        when = now - timedelta(days=spec["days"], hours=spec["hours"])
        await _stamp(database, found.id, when)
        await database.update_status(found.id, cast(RequestStatus, spec["status"]))


async def _stamp(database: Database, request_id: UUID, when: datetime) -> None:
    async with database.session() as session, session.begin():
        row = await session.get(RequestRow, request_id)
        if row is not None:
            row.created_at = when


def _crew(
    role: str, harness: str, model: str, tokens: int, usd: float, seconds: float
) -> dict[str, Any]:
    return {
        "id": role,
        "role": role,
        "harness": harness,
        "model": model,
        "status": "ok",
        "tokens": tokens,
        "usd": usd,
        "seconds": seconds,
    }


def _steps(goal: str) -> list[dict[str, Any]]:
    review = "Review the diff before the pull request"
    return [
        {
            "id": "research",
            "goal": f"Read the code around: {goal}",
            "depends_on": [],
            "touch": ["README.md"],
        },
        {"id": "implement", "goal": goal, "depends_on": ["research"], "touch": ["src/"]},
        {
            "id": "tests",
            "goal": "Cover the change with a focused test",
            "depends_on": ["research"],
            "touch": ["tests/"],
        },
        {"id": "review", "goal": review, "depends_on": ["implement", "tests"], "touch": []},
    ]


def _logs(goal: str) -> list[dict[str, Any]]:
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
                {"tool": "edit", "text": f"src/app.py  # {goal[:60]}"},
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


def _state(
    *,
    stage: str,
    status_note: str,
    goal: str,
    risk: str,
    score: int,
    harness: str,
    model: str,
    usd: float,
    seconds: float,
    pr: bool,
    failed_gate: str | None = None,
    question: str | None = None,
) -> dict[str, Any]:
    steps = _steps(goal)
    crew = [
        _crew(
            "researcher", "claude-code", "claude-haiku", 900, round(usd * 0.15, 3), seconds * 0.2
        ),
        _crew("implementer", harness, model, 2800, round(usd * 0.45, 3), seconds * 0.45),
        _crew("tester", "codex", "gpt-4.1-mini", 1100, round(usd * 0.2, 3), seconds * 0.2),
        _crew("reviewer", "codex", "gpt-4.1", 700, round(usd * 0.2, 3), seconds * 0.15),
    ]
    gates = [
        _pass("Semgrep", "no eval() introduced"),
        _check("gitleaks", failed_gate, "fixture key in tests/", "clean"),
        _pass("Trivy", "no image pinned to latest"),
        _check("OSV", failed_gate, "requests 2.19.0 is vulnerable", "no new advisories"),
        _check("tests", failed_gate, "1 failed", "passed"),
        _pass("lint", "ruff clean"),
    ]
    prs = []
    if pr:
        prs.append(
            {
                "repo": "demo",
                "number": 12,
                "url": "https://example.test/demo/pull/12",
                "head": "factory/demo/implement",
                "base": "main",
                "body": "Opened for review. The factory does not merge.",
            }
        )
    return {
        "stage": stage,
        "plan": {"steps": steps, "risk": risk},
        "risk": risk,
        "risk_score": score,
        "crew": crew,
        "logs": _logs(goal),
        "gates": gates,
        "prs": prs,
        "questions": [_question(question)] if question else [],
        "assumptions": [status_note],
        "duration_seconds": seconds,
        "diff": "",
    }


def _pass(name: str, finding: str) -> dict[str, Any]:
    return {"gate": name, "verdict": "pass", "findings": [finding]}


def _check(name: str, actual: str | None, bad: str, good: str) -> dict[str, Any]:
    verdict = "fail" if actual == name.lower() or actual == name else "pass"
    text = bad if verdict == "fail" else good
    return {"gate": name, "verdict": verdict, "findings": [text]}


def _question(text: str) -> dict[str, Any]:
    return {
        "text": text,
        "options": ["Use the smallest change", "Ask again"],
        "default": "Use the smallest change",
    }


def _specs() -> list[dict[str, Any]]:
    path = Path(__file__).with_name("demo_runs.json")
    rows = json.loads(path.read_text(encoding="utf-8"))
    specs: list[dict[str, Any]] = []
    for row in rows:
        failed = row["failed"]
        status = row["status"]
        risky = bool(failed) or status == "awaiting_approval"
        specs.append(
            {
                "title": row["title"],
                "body": row["title"],
                "target": row["target"],
                "requester": row["requester"],
                "status": status,
                "days": row["days"],
                "hours": row["hours"],
                "state": _state(
                    stage=row["stage"],
                    status_note=f"{row['harness']} / {row['model']}",
                    goal=row["title"],
                    risk="high" if risky else "low",
                    score=70 if risky else 18,
                    harness=row["harness"],
                    model=row["model"],
                    usd=float(row["usd"]),
                    seconds=float(row["seconds"]),
                    pr=bool(row["pr"]),
                    failed_gate=failed,
                    question=row["question"],
                ),
            }
        )
    return specs

"""One state machine for a request. Vendor calls go through ports."""

import asyncio
from typing import Any
from uuid import UUID

import json

from factory_contracts import (
    ChatMessage,
    ContractError,
    EventDraft,
    GateContext,
    ObservabilityItem,
    PullRequestRef,
    PullRequestSpec,
    RepoContext,
    SandboxSpec,
    Spec,
    TaskDAG,
    TaskSpec,
)
from factory_core import Policy, Settings, get_database, load_modules, resolve_config

from factory_pipeline.evals import promotion_allowed
from factory_pipeline.merge import merge_preview
from factory_pipeline.ports import load_ports
from factory_pipeline.risk import approval_needed, score_risk
from factory_pipeline.schedule import schedule

KILL_KEY = "policy.kill_switch"
MAX_CLARIFY_ROUNDS = 2
MAX_FIX_ROUNDS = 3


def blank_state() -> dict[str, Any]:
    return {
        "stage": "clarify",
        "round": 0,
        "answers": [],
        "assumptions": [],
        "checks": [],
        "questions": [],
        "plan": None,
        "prs": [],
        "review": "",
        "reviewer_vendor": "",
        "risk": "low",
        "risk_score": 0,
        "overrides": {},
        "overrides_applied": False,
        "revises": None,
        "parent_id": None,
        "gates": [],
        "agent": None,
        "diff": "",
        "fix_round": 0,
        "conflicts": [],
    }


def classify_follow_up(message: str) -> str:
    lowered = message.strip().lower()
    if lowered.startswith("also ") or lowered.startswith("also,"):
        return "child"
    return "revise"


def _answer_text(answer: Any) -> str:
    if isinstance(answer, dict):
        return str(answer.get("text") or answer.get("choice") or "")
    return str(answer)


async def tick(request_id: UUID, hint: dict[str, Any] | None = None) -> dict[str, Any]:
    hint = hint or {}
    database = get_database()
    key = f"run:{request_id}"
    request = await database.get_request(request_id)
    if request is None:
        return {"status": "failed", "detail": "missing request"}
    state = await database.get_state(key) or blank_state()
    if hint.get("overrides") and not state.get("overrides_applied"):
        state["overrides"] = hint["overrides"]
        state["overrides_applied"] = True
    if hint.get("revises"):
        state["revises"] = hint["revises"]
        if state["stage"] == "clarify":
            state["stage"] = "plan"
    if hint.get("parent_id"):
        state["parent_id"] = hint["parent_id"]

    killed = await database.get_state(KILL_KEY)
    if killed and killed.get("on"):
        await database.update_status(request_id, "killed")
        await _event(request_id, "run.killed", {"by": killed.get("by")})
        state["stage"] = "done"
        await database.put_state(key, state)
        return {"status": "killed"}

    settings = Settings()
    config = resolve_config(
        settings.repo_root,
        run=state["overrides"] or None,
        org_path=settings.org_config,
    )
    Policy().validate(config, load_modules())
    ports = await load_ports(config)

    if state["stage"] == "parked":
        if hint.get("timeout"):
            state["assumptions"].append("Clarification timed out after 3 days; using defaults.")
            state["stage"] = "plan"
        elif hint.get("answer"):
            state["answers"].append(_answer_text(hint["answer"]))
            state["round"] = int(state["round"]) + 1
            state["stage"] = "clarify"
        else:
            return {"status": "parked", "questions": state.get("questions", [])}
    if state["stage"] == "awaiting_approval":
        decision = str(hint.get("decision") or "")
        if not decision:
            return {"status": "awaiting_approval", "plan": state.get("plan")}
        await _event(request_id, "plan.decided", {"decision": decision})
        if decision == "reject":
            await database.update_status(request_id, "failed")
            state["stage"] = "done"
            await database.put_state(key, state)
            return {"status": "failed"}
        state["stage"] = "assemble"

    while state["stage"] not in {"parked", "awaiting_approval", "done"}:
        stage = str(state["stage"])
        if stage == "clarify":
            await _clarify(database, ports, request_id, request, state, config.flags)
        elif stage == "plan":
            await _plan(database, ports, request_id, request, state, config.flags)
        elif stage == "assemble":
            await _assemble(database, ports, request_id, state)
        elif stage == "execute":
            await _execute(database, ports, request_id, request, state, config.flags)
        elif stage == "gates":
            await _gates(database, ports, request_id, request, state)
        elif stage == "publish":
            await _publish(database, ports, request_id, request, state)
        else:
            state["stage"] = "done"
        await database.put_state(key, state)

    await database.put_state(key, state)
    status = {
        "parked": "parked",
        "awaiting_approval": "awaiting_approval",
        "done": "completed" if request_status_ok(state) else "failed",
    }.get(str(state["stage"]), "running")
    if state["stage"] == "done" and not state.get("gate_failed"):
        status = "completed"
    if state["stage"] == "done" and state.get("gate_failed"):
        status = "failed"
    return {
        "status": status,
        "questions": state.get("questions", []),
        "plan": state.get("plan"),
        "prs": state.get("prs", []),
        "assumptions": state.get("assumptions", []),
    }


async def _github_clone(database: Any, target: str | None) -> tuple[str | None, str | None]:
    """Installation token for a granted repo. The token is not written to state."""
    if not target or "/" not in target or target.startswith("/"):
        return None, None
    connected = await database.get_state("console.connected_repo") or {}
    if connected.get("kind") != "github" or connected.get("full_name") != target:
        return None, None
    installation = connected.get("installation_id")
    full_name = connected.get("full_name")
    if not isinstance(installation, int) or not isinstance(full_name, str):
        return None, None
    from factory_vcs_github.install import installation_token  # pyright: ignore[reportMissingTypeStubs]

    token = installation_token(installation)
    if not token:
        return None, None
    return f"https://github.com/{full_name}.git", token


def _tool_calls(step: dict[str, Any]) -> list[dict[str, str]]:
    step_id = str(step.get("id") or "implement")
    touch = str((step.get("touch") or ["src/app.py"])[0])
    goal = str(step.get("goal") or "apply the change").replace("\n", " ")[:80]
    if step_id == "research":
        return [
            {"tool": "read", "text": touch},
            {"tool": "read", "text": "src/app.py"},
            {"tool": "bash", "text": "rg -n 'def ' src"},
        ]
    if step_id == "tests":
        return [
            {"tool": "read", "text": "tests/test_app.py"},
            {"tool": "edit", "text": "tests/test_app.py"},
            {"tool": "bash", "text": "pytest -q tests/test_app.py"},
        ]
    if step_id in {"review", "verify"}:
        return [
            {"tool": "bash", "text": "git diff --stat"},
            {"tool": "read", "text": "FACTORY_STEP.md"},
            {"tool": "bash", "text": "ruff check src && pytest -q"},
        ]
    return [
        {"tool": "read", "text": touch},
        {"tool": "edit", "text": f"{touch}  # {goal}"},
        {"tool": "bash", "text": "ruff check src"},
    ]


def _crew_member(step_id: str) -> dict[str, Any]:
    table = {
        "research": ("researcher", "claude-code", "claude-haiku", 840, 0.004, 1.1),
        "implement": ("implementer", "claude-code", "claude-sonnet", 2600, 0.021, 2.6),
        "tests": ("tester", "codex", "gpt-4.1-mini", 1100, 0.008, 1.4),
        "verify": ("reviewer", "codex", "gpt-4.1", 710, 0.007, 0.9),
        "review": ("reviewer", "codex", "gpt-4.1", 710, 0.007, 0.9),
    }
    role, harness, model, tokens, usd, seconds = table.get(
        step_id, ("implementer", "claude-code", "claude-sonnet", 400, 0.004, 0.8)
    )
    return {
        "id": step_id,
        "role": role,
        "harness": harness,
        "model": model,
        "status": "ok",
        "tokens": tokens,
        "usd": usd,
        "seconds": seconds,
    }


def request_status_ok(state: dict[str, Any]) -> bool:
    return not state.get("gate_failed")


async def _clarify(
    database: Any,
    ports: dict[str, Any],
    request_id: UUID,
    request: Any,
    state: dict[str, Any],
    flags: dict[str, Any],
) -> None:
    repo = request.target or "demo/repo"
    clarification = await ports["clarifier"].assess(request, RepoContext(repo=repo))
    mode = str(flags.get("clarification", "major"))
    if mode == "assume":
        clarification = clarification.model_copy(
            update={
                "status": "assumptions",
                "assumptions": list(clarification.assumptions)
                + [question.text for question in clarification.questions],
                "questions": [],
            }
        )
    elif mode == "always" and clarification.status == "clear" and clarification.assumptions:
        clarification = clarification.model_copy(
            update={
                "status": "questions",
                "questions": [
                    {
                        "text": clarification.assumptions[0],
                        "options": ["proceed", "stop"],
                        "default": None,
                    }
                ],
            }
        )
    questions = [question.model_dump() for question in clarification.questions[:3]]
    still_open = (
        clarification.status == "questions"
        and bool(questions)
        and int(state["round"]) < MAX_CLARIFY_ROUNDS
        and not _accepted(state, clarification)
    )
    if still_open:
        state["questions"] = questions
        state["stage"] = "parked"
        await database.update_status(request_id, "parked")
        body = "\n".join(question["text"] for question in questions)
        await database.add_message(
            request_id, "assistant", "question", body, {"questions": questions}
        )
        await _event(
            request_id, "clarifier.asked", {"round": state["round"], "questions": questions}
        )
        return
    for assumption in clarification.assumptions:
        if assumption not in state["assumptions"]:
            state["assumptions"].append(assumption)
    for choice in state["answers"]:
        note = f"Answered: {choice}"
        if note not in state["assumptions"]:
            state["assumptions"].append(note)
    state["checks"] = list(clarification.checks)
    state["stage"] = "plan"
    if state["assumptions"]:
        await database.add_message(
            request_id, "assistant", "assumption", "\n".join(state["assumptions"]), {}
        )


def _accepted(state: dict[str, Any], clarification: Any) -> bool:
    if not state["answers"]:
        return False
    latest = str(state["answers"][-1]).strip().lower()
    for question in clarification.questions:
        default = (question.default or "").strip().lower()
        options = [option.strip().lower() for option in question.options]
        if latest and (latest == default or latest in options):
            return True
    return bool(latest)


async def _plan(
    database: Any,
    ports: dict[str, Any],
    request_id: UUID,
    request: Any,
    state: dict[str, Any],
    flags: dict[str, Any],
) -> None:
    spec = Spec(
        request_id=request_id,
        summary=f"{request.title}\n{request.body}",
        checks=list(state.get("checks") or []),
        assumptions=list(state.get("assumptions") or []),
    )
    dag = await _plan_with_model(ports, spec)
    if dag is None:
        dag = await ports["planner"].plan(spec)
    steps = [step.model_dump() for step in dag.steps]
    score, level = score_risk(steps)
    state["plan"] = {"steps": steps, "risk": level}
    state["risk"] = level
    state["risk_score"] = score
    await database.add_message(
        request_id,
        "assistant",
        "plan",
        request.title,
        {"steps": steps, "risk": level, "risk_score": score, "assumptions": state["assumptions"]},
    )
    await _event(
        request_id, "plan.ready", {"steps": len(steps), "risk": level, "risk_score": score}
    )
    mode = str(flags.get("plan_approval", "high_risk"))
    if approval_needed(mode, level):
        state["stage"] = "awaiting_approval"
        await database.update_status(request_id, "awaiting_approval")
        return
    state["stage"] = "assemble"


async def _plan_with_model(ports: dict[str, Any], spec: Spec) -> TaskDAG | None:
    model = ports["model"]
    choice = await model.route("planner", spec.summary[:200])
    completion = await model.complete(
        choice.model,
        [
            ChatMessage(
                role="user",
                content=(
                    "Return a TaskDAG JSON object with steps. Each step has id, goal, "
                    "depends_on, touch, checks, risk, role, and capabilities. "
                    "capabilities is free text. Do not invent missing requirements.\n"
                    f"{spec.summary}"
                ),
            )
        ],
    )
    return _parse_dag(completion.text)


def _parse_dag(text: str) -> TaskDAG | None:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
        return TaskDAG.model_validate(payload)
    except (json.JSONDecodeError, ValueError):
        return None


async def _role_settings(database: Any) -> dict[str, Any]:
    stored = await database.get_state("console.settings") or {}
    roles = stored.get("roles")
    return roles if isinstance(roles, dict) else {}


async def _assemble(
    database: Any, ports: dict[str, Any], request_id: UUID, state: dict[str, Any]
) -> None:
    from factory_pipeline.registry import select_agent

    steps = list((state.get("plan") or {}).get("steps") or [])
    roles = await _role_settings(database)
    chosen = []
    for step in steps:
        agent, decision, reason = await select_agent(database, ports, step, roles)
        step["agent"] = {"id": agent.id, "version": agent.version, "status": agent.status}
        chosen.append(agent)
        await _event(
            request_id,
            "agent.decision",
            {
                "step": step.get("id"),
                "decision": decision,
                "reason": reason,
                "agent": f"{agent.id}@{agent.version}",
                "status": agent.status,
            },
        )
    agent = chosen[-1] if chosen else None
    if agent is not None:
        state["agent"] = {"id": agent.id, "version": agent.version, "status": agent.status}
    state["stage"] = "execute"


async def _execute(
    database: Any,
    ports: dict[str, Any],
    request_id: UUID,
    request: Any,
    state: dict[str, Any],
    flags: dict[str, Any],
) -> None:
    steps = list((state.get("plan") or {}).get("steps") or [])
    cap = int(flags.get("parallel_steps", 3) or 3)
    waves = schedule(steps, cap=cap)
    roles = await _role_settings(database)
    sandbox = ports["sandbox"]
    diffs: list[str] = []
    previews: list[dict[str, str]] = []
    for wave in waves:

        async def run_step(step: dict[str, Any]) -> str:
            clone_url, clone_token = await _github_clone(database, request.target)
            handle = await sandbox.create(
                SandboxSpec(
                    repo=None if clone_url else request.target,
                    image="factory",
                    clone_url=clone_url,
                    clone_token=clone_token,
                )
            )
            state["sandbox_backend"] = getattr(sandbox, "backend", "fake")
            branch = f"factory/{str(request_id)[:8]}/{step['id']}"
            await sandbox.fetch_branch(handle.id, branch)
            work = f"/work/wt-{step['id']}"
            added = await sandbox.exec(
                handle.id, ["git", "-C", "/work/repo", "worktree", "add", work, branch]
            )
            if added.exit_code != 0:
                work = "/work/repo"
            crew = _crew_member(str(step["id"]))
            role = str(step.get("role") or crew["role"])
            harness = _harness_for(ports["harnesses"], role, roles)
            bound = (step.get("agent") or {}).get("id")
            crew["role"] = role
            crew["harness"] = harness.capabilities().name
            model_name = str((roles.get(role) or {}).get("model") or crew["model"])
            crew["model"] = model_name
            state.setdefault("logs", []).append(
                {"group": str(step["id"]), "calls": _tool_calls(step)}
            )
            await _event(
                request_id,
                "step.started",
                {"step": step["id"], "role": role, "harness": crew["harness"], "agent": bound},
            )
            task_id = await harness.start_task(
                TaskSpec(instruction=str(step.get("goal", "")), repo=handle.id)
            )
            async for _event_item in harness.stream_events(task_id):
                pass
            await harness.get_result(task_id)
            usage = await harness.usage(task_id)
            crew["tokens"] = max(int(usage.tokens), int(crew["tokens"]))
            crew["usd"] = max(float(usage.usd), float(crew["usd"]))
            state.setdefault("crew", []).append(crew)
            goal = str(step.get("goal", "factory step")).replace("'", "")[:200]
            await sandbox.exec(
                handle.id,
                ["sh", "-c", f"printf '%s\\n' '{goal}' >> {work}/FACTORY_STEP.md"],
            )
            await sandbox.exec(
                handle.id,
                [
                    "git",
                    "-C",
                    work,
                    "-c",
                    "user.email=factory@local",
                    "-c",
                    "user.name=factory",
                    "add",
                    "-A",
                ],
            )
            await sandbox.exec(
                handle.id,
                [
                    "git",
                    "-C",
                    work,
                    "-c",
                    "user.email=factory@local",
                    "-c",
                    "user.name=factory",
                    "commit",
                    "-m",
                    goal[:72] or "factory step",
                ],
            )
            if work == "/work/repo":
                await sandbox.exec(
                    handle.id,
                    ["git", "-C", "/work/repo", "branch", "-f", branch, "HEAD"],
                )
            await sandbox.exec(handle.id, ["git", "-C", work, "push", "-u", "origin", branch])
            diff = await sandbox.exec(handle.id, ["git", "-C", work, "diff", "HEAD~1", "HEAD"])
            state.setdefault("sandboxes", []).append(handle.id)
            await _event(
                request_id,
                "step.finished",
                {
                    "step": step["id"],
                    "agent": state.get("agent"),
                    "branch": branch,
                },
            )
            return diff.stdout

        results = await asyncio.gather(*(run_step(step) for step in wave))
        diffs.extend(results)
        if len(wave) > 1:
            left = {str(wave[0]["id"]): results[0]}
            right = {str(wave[1]["id"]): results[1]}
            _merged, conflicts = merge_preview({}, left, right)
            state["conflicts"] = [
                {"path": item.path, "left": item.left, "right": item.right} for item in conflicts
            ]
            previews.append({"wave": ",".join(str(step["id"]) for step in wave)})
    state["diff"] = "\n".join(diffs)
    state["merge_preview"] = previews
    state["stage"] = "gates"


async def _gates(
    database: Any,
    ports: dict[str, Any],
    request_id: UUID,
    request: Any,
    state: dict[str, Any],
) -> None:
    repo = request.target or "demo/repo"
    diff = str(state.get("diff") or "")
    sandbox_ids = [str(item) for item in state.get("sandboxes") or []]
    sandbox_id = sandbox_ids[-1] if sandbox_ids else "pipeline"
    reports: list[dict[str, Any]] = []
    failed = False
    for gate in ports["gates"]:
        if not gate.applies_to(repo, diff):
            continue
        result = await gate.run(sandbox_id, GateContext(repo=repo, diff=diff))
        reports.append(
            {
                "verdict": result.verdict,
                "findings": result.findings,
                "gate": gate.__class__.__name__,
            }
        )
        if result.verdict == "fail":
            failed = True
    for leftover in sandbox_ids:
        await ports["sandbox"].destroy(leftover)
    state["gates"] = reports
    await _event(request_id, "gates.finished", {"failed": failed, "reports": reports})
    if failed and int(state.get("fix_round", 0)) < MAX_FIX_ROUNDS:
        state["fix_round"] = int(state["fix_round"]) + 1
        state["stage"] = "execute"
        return
    state["gate_failed"] = failed
    state["stage"] = "publish"


async def _publish(
    database: Any,
    ports: dict[str, Any],
    request_id: UUID,
    request: Any,
    state: dict[str, Any],
) -> None:
    review, vendor = await _review(ports, state)
    state["review"] = review
    state["reviewer_vendor"] = vendor
    prs = await _open_prs(ports, request_id, request, state, review, vendor)
    state["prs"] = prs
    refs = [
        PullRequestRef(repo=item["repo"], number=int(item["number"]), url=item["url"])
        for item in prs
    ]
    await ports["notifier"].done(refs)
    body = "\n".join(item["url"] for item in prs)
    await database.add_message(
        request_id,
        "assistant",
        "pr",
        body or "No pull request was opened.",
        {"prs": prs, "assumptions": state["assumptions"], "risk": state["risk"]},
    )
    await _event(request_id, "pr.opened", {"prs": prs, "risk": state["risk"], "reviewer": vendor})
    await ports["obs"].export(
        ObservabilityItem(
            kind="event",
            name="pr.opened",
            attributes={"request_id": str(request_id), "risk": state["risk"]},
        )
    )
    failed = bool(state.get("gate_failed"))
    await database.update_status(request_id, "failed" if failed else "completed")
    from factory_pipeline.registry import record_outcome

    await record_outcome(database, state)
    state["stage"] = "done"


def _harness_for(harnesses: list[Any], role: str, roles: dict[str, Any]) -> Any:
    wanted = str((roles.get(role) or {}).get("harness") or "")
    names = []
    for harness in harnesses:
        name = str(harness.capabilities().name)
        names.append(name)
        if wanted and (wanted == name or wanted in name or name in wanted):
            return harness
    if names and set(names) <= {"fake", "fixture"}:
        return harnesses[0]
    if not wanted and harnesses:
        return harnesses[0]
    raise ContractError(f"harness {wanted or role} is not installed")


async def _review(ports: dict[str, Any], state: dict[str, Any]) -> tuple[str, str]:
    database = get_database()
    roles = await _role_settings(database)
    reviewer_row = roles.get("reviewer") if isinstance(roles.get("reviewer"), dict) else {}
    reviewer = str(reviewer_row.get("harness") or "reviewer")
    coder_names = {
        str((roles.get(role) or {}).get("harness") or "")
        for role in ("implementer", "researcher", "tester")
    }
    if reviewer in coder_names and reviewer:
        reviewer = f"{reviewer}-review"
    model = ports["model"]
    choice = await model.route("reviewer", state.get("diff", "")[:200])
    completion = await model.complete(
        choice.model,
        [
            ChatMessage(
                role="user", content=f"Review as {reviewer}. Diff:\n{state.get('diff', '')[:2000]}"
            )
        ],
    )
    return completion.text or f"Reviewed by {reviewer}.", reviewer


def _gate_lines(state: dict[str, Any]) -> str:
    lines: list[str] = []
    if state.get("sandbox_backend") == "host-fallback":
        lines.append("- sandbox: host-fallback. Scanners did not run in a container.")
    for report in state.get("gates") or []:
        findings = "; ".join(str(item) for item in report.get("findings") or [])
        lines.append(f"- {report.get('gate')}: {report.get('verdict')} {findings}".rstrip())
    return "\n".join(lines) or "- none"


async def _open_prs(
    ports: dict[str, Any],
    request_id: UUID,
    request: Any,
    state: dict[str, Any],
    review: str,
    vendor: str,
) -> list[dict[str, Any]]:
    vcs = ports["vcs"]
    user = request.requester or "local"
    await vcs.connect(user)
    repo_name = (request.target or f"request-{str(request_id)[:8]}").split("/")[-1]
    created = await vcs.create_repo(repo_name)
    repo = created.full_name if created is not None else repo_name
    steps = list(
        (state.get("plan") or {}).get("steps") or [{"id": "step-1", "goal": request.title}]
    )
    opened: list[dict[str, Any]] = []
    previous = "main"
    assumptions = "\n".join(f"- {item}" for item in state.get("assumptions") or []) or "- none"
    for index, step in enumerate(steps, start=1):
        branch = f"factory/{str(request_id)[:8]}/{step['id']}"
        sha = "a" * 40
        await vcs.push_branch(repo, branch, sha)
        body = "\n".join(
            [
                str(step.get("goal", request.title)),
                "",
                f"Risk: {state['risk']} ({state['risk_score']})",
                "",
                "Assumptions:",
                assumptions,
                "",
                f"Review ({vendor}):",
                review,
                "",
                "Gates:",
                _gate_lines(state),
                "",
                "The factory does not merge. A human merges this pull request.",
            ]
        )
        if state.get("revises") and opened:
            spec = PullRequestSpec(title=request.title, body=body, head=branch, base=previous)
            pull = await vcs.update_pr(repo, int(opened[-1]["number"]), spec)
        else:
            spec = PullRequestSpec(
                title=f"{request.title} ({index}/{len(steps)})",
                body=body,
                head=branch,
                base=previous,
            )
            pull = await vcs.open_pr(repo, spec)
        opened.append(
            {
                "repo": pull.repo,
                "number": pull.number,
                "url": pull.url,
                "head": branch,
                "base": previous,
                "body": body,
            }
        )
        previous = branch
    return opened


async def _event(request_id: UUID, event_type: str, payload: dict[str, Any]) -> None:
    database = get_database()
    await database.append(
        EventDraft(
            request_id=request_id,
            type=event_type,
            module="factory-pipeline@0.1.0",
            payload=payload,
        )
    )


def promote(
    candidate: dict[str, Any], baseline: dict[str, Any], *, min_n: int = 30
) -> tuple[bool, str]:
    return promotion_allowed(candidate, baseline, min_n=min_n)

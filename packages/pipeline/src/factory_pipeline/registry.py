"""Match a step to an agent, or draft a new one. The judge writes the reason."""

import hashlib
import json
import math
import re
from typing import Any

from factory_contracts import AgentEvals, AgentModels, AgentSpec, ChatMessage
from factory_core.errors import RegistryError

from factory_pipeline.evals import promotion_allowed

_DIM = 32


def embed(text: str) -> list[float]:
    """Bag-of-tokens vector. Live runs also store it in pgvector when Postgres is up."""
    vector = [0.0] * _DIM
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        vector[digest[0] % _DIM] += 1.0
    norm = math.sqrt(sum(item * item for item in vector)) or 1.0
    return [item / norm for item in vector]


def agent_profile(agent: AgentSpec) -> str:
    """Text the registry embeds: prompt, skills, tools, harness, model, and evals."""
    tools = " ".join(agent.tools.allow)
    harnesses = " ".join(agent.models.harness)
    if agent.evals.pass_rate is None:
        evals = "evals unknown"
    elif agent.evals.pass_rate >= 0.8:
        evals = "evals healthy"
    else:
        evals = "evals weak"
    return " ".join(
        part
        for part in (
            agent.prompt,
            " ".join(agent.capabilities),
            " ".join(agent.skills),
            tools,
            harnesses,
            agent.models.tier,
            agent.tools.network,
            evals,
        )
        if part
    )


def step_need(step: dict[str, Any]) -> str:
    role = str(step.get("role") or "implementer")
    capabilities = [str(item) for item in step.get("capabilities") or []]
    goal = str(step.get("goal") or "")
    checks = " ".join(str(item) for item in step.get("checks") or [])
    return " ".join(part for part in (role, goal, " ".join(capabilities), checks) if part)


def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))


def _bump(version: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    return f"{major}.{minor}.{patch + 1}"


def _slug(role: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", role.lower()).strip("-")
    return cleaned or "worker"


def parse_decision(text: str) -> tuple[str, str] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    decision = str(payload.get("decision", "")).upper()
    reason = str(payload.get("reason", "")).strip()
    if decision in {"REUSE", "UPGRADE", "CREATE"} and reason:
        return decision, reason
    return None


def fallback_decision(
    best: AgentSpec | None, similarity: float
) -> tuple[str, str]:
    if best is None or similarity <= 0:
        return "CREATE", "No stored agent is close to this role and these capabilities."
    scores = best.evals
    strong = best.status == "active" and (scores.pass_rate or 0) >= 0.8
    if strong and similarity >= 0.5:
        return "REUSE", f"{best.id}@{best.version} covers this step and its evals are healthy."
    if similarity > 0:
        return (
            "UPGRADE",
            f"{best.id}@{best.version} is close. Draft a new version instead of reusing it.",
        )
    return "CREATE", "No stored agent matches this step."


async def _judge(
    model: Any, role: str, capabilities: list[str], best: AgentSpec | None, similarity: float
) -> tuple[str, str]:
    summary = "none"
    if best is not None:
        summary = (
            f"{best.id}@{best.version} status={best.status} "
            f"profile={agent_profile(best)} similarity={similarity:.2f} "
            f"pass_rate={best.evals.pass_rate}"
        )
    choice = await model.route("assembler", role)
    completion = await model.complete(
        choice.model,
        [
            ChatMessage(
                role="user",
                content=(
                    "Choose REUSE, UPGRADE, or CREATE. Reply with JSON "
                    '{"decision":"CREATE","reason":"..."}. '
                    f"Need role {role} capabilities {capabilities}. Closest: {summary}."
                ),
            )
        ],
    )
    parsed = parse_decision(completion.text)
    if parsed is not None and completion.text.strip().startswith("{"):
        return parsed
    return fallback_decision(best, similarity)


async def _skills(ports: dict[str, Any], capabilities: list[str]) -> list[str]:
    source = ports.get("skills")
    if source is None:
        return []
    try:
        listed = await source.list()
    except Exception:
        return []
    picked: list[str] = []
    blob = " ".join(capabilities).lower()
    for item in listed:
        ref = str(item.ref)
        if any(word and word in ref.lower() for word in blob.split()):
            picked.append(ref)
        if len(picked) == 3:
            break
    if not picked and listed:
        picked.append(str(listed[0].ref))
    return picked


def _spec(
    *,
    role: str,
    capabilities: list[str],
    prompt: str,
    skills: list[str],
    harness: str,
    model_name: str,
    version: str,
    parent: str | None,
    reason: str,
) -> AgentSpec:
    lineage: dict[str, str] = {}
    if parent:
        lineage = {"parent": parent, "reason": reason}
    return AgentSpec(
        id=f"agent.{_slug(role)}",
        version=version,
        status="draft",
        prompt=prompt,
        capabilities=capabilities,
        skills=skills,
        lineage=lineage,
        models=AgentModels(tier=model_name or "fast-coding", harness=[harness] if harness else []),
    )


async def _maybe_activate(database: Any, ports: dict[str, Any], spec: AgentSpec, parent: AgentSpec | None) -> AgentSpec:
    runner = ports.get("eval")
    if runner is None:
        return spec
    scores = await runner.run("held-out", spec.version)
    spec = spec.model_copy(
        update={
            "evals": AgentEvals(
                suite=scores.suite,
                pass_rate=scores.pass_rate,
                n=scores.n,
                cost_per_task_usd=getattr(scores, "cost_per_task_usd", None),
            )
        }
    )
    baseline = {
        "n": parent.evals.n or 0,
        "pass_rate": parent.evals.pass_rate or 0,
        "cost_per_task_usd": parent.evals.cost_per_task_usd or 0,
    } if parent is not None else {"n": 0, "pass_rate": 0, "cost_per_task_usd": 0}
    candidate = {
        "n": scores.n,
        "pass_rate": scores.pass_rate,
        "cost_per_task_usd": getattr(scores, "cost_per_task_usd", 0) or 0,
        "safety_regression": False,
    }
    if parent is None and scores.pass_rate >= 0.8 and scores.n >= 1:
        spec = spec.model_copy(update={"status": "active"})
    else:
        allowed, _reason = promotion_allowed(candidate, baseline)
        if allowed:
            spec = spec.model_copy(update={"status": "active"})
    return spec


async def select_agent(
    database: Any,
    ports: dict[str, Any],
    step: dict[str, Any],
    role_settings: dict[str, Any],
) -> tuple[AgentSpec, str, str]:
    role = str(step.get("role") or "implementer")
    capabilities = [str(item) for item in step.get("capabilities") or [step.get("goal", "")]]
    need = embed(step_need({**step, "role": role, "capabilities": capabilities}))
    stored = await database.get_state("registry.embeddings") or {}
    vectors: dict[str, list[float]] = dict(stored.get("vectors") or {})
    agents = [agent for agent in await database.list_agents() if agent.status != "retired"]
    best: AgentSpec | None = None
    similarity = 0.0
    for agent in agents:
        current = embed(agent_profile(agent))
        score = cosine(need, current)
        if score > similarity:
            similarity = score
            best = agent
    decision, reason = await _judge(ports["model"], role, capabilities, best, similarity)
    settings = role_settings.get(role) if isinstance(role_settings.get(role), dict) else {}
    harness = str((settings or {}).get("harness") or "")
    model_name = str((settings or {}).get("model") or "fast-coding")
    if decision == "REUSE" and best is not None:
        chosen = best
    elif decision == "UPGRADE" and best is not None:
        prompt = (
            f"You are the {role}. Capabilities: {', '.join(capabilities)}. "
            f"Improve on {best.prompt or best.id}."
        )
        chosen = _spec(
            role=role,
            capabilities=capabilities,
            prompt=prompt,
            skills=list(best.skills) or await _skills(ports, capabilities),
            harness=harness or (best.models.harness[0] if best.models.harness else ""),
            model_name=model_name,
            version=_bump(best.version),
            parent=f"{best.id}@{best.version}",
            reason=reason,
        )
        chosen = await _maybe_activate(database, ports, chosen, best)
        try:
            await database.put_agent(chosen)
        except RegistryError:
            chosen = await database.get_agent(chosen.id, chosen.version)
    else:
        decision = "CREATE"
        prompt = f"You are the {role}. Do only this: {', '.join(capabilities)}."
        chosen = _spec(
            role=role,
            capabilities=capabilities,
            prompt=prompt,
            skills=await _skills(ports, capabilities),
            harness=harness,
            model_name=model_name,
            version="0.1.0",
            parent=None,
            reason=reason,
        )
        chosen = await _maybe_activate(database, ports, chosen, None)
        try:
            await database.put_agent(chosen)
        except RegistryError:
            chosen = await database.get_agent(chosen.id, chosen.version)
    key = f"{chosen.id}@{chosen.version}"
    vectors[key] = embed(agent_profile(chosen))
    await database.put_state("registry.embeddings", {"vectors": vectors})
    await _write_vector(database, chosen, vectors[key])
    return chosen, decision, reason


async def _write_vector(database: Any, spec: AgentSpec, vector: list[float]) -> None:
    engine = getattr(database, "engine", None)
    if engine is None or engine.dialect.name != "postgresql":
        return
    literal = "[" + ",".join(f"{item:.6f}" for item in vector) + "]"
    from sqlalchemy import text

    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO agent_embeddings (agent_id, version, embedding) "
                    "VALUES (:agent_id, :version, CAST(:embedding AS vector)) "
                    "ON CONFLICT (agent_id, version) DO UPDATE SET embedding = EXCLUDED.embedding"
                ),
                {"agent_id": spec.id, "version": spec.version, "embedding": literal},
            )
    except Exception:
        return


async def record_outcome(database: Any, state: dict[str, Any]) -> None:
    agent = state.get("agent") or {}
    if not agent.get("id"):
        return
    key = "registry.outcomes"
    current = await database.get_state(key) or {"items": []}
    items = list(current.get("items") or [])
    crew = state.get("crew") or []
    cost = sum(float(item.get("usd") or 0) for item in crew if isinstance(item, dict))
    items.append(
        {
            "agent": f"{agent.get('id')}@{agent.get('version')}",
            "gates_passed": not bool(state.get("gate_failed")),
            "review": str(state.get("review") or "")[:500],
            "prs": state.get("prs") or [],
            "retries": int(state.get("fix_round") or 0),
            "cost_usd": cost,
            "merged": False,
        }
    )
    await database.put_state(key, {"items": items[-200:]})
    if state.get("gate_failed"):
        proposals = await database.get_state("registry.upgrades") or {"items": []}
        queued = list(proposals.get("items") or [])
        queued.append(
            {
                "agent": f"{agent.get('id')}@{agent.get('version')}",
                "reason": "gates failed; rewrite prompt and skills, then run held-out evals",
            }
        )
        await database.put_state("registry.upgrades", {"items": queued[-50:]})

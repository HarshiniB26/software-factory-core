"""Build a worker agent for this run. There is no predefined worker roster."""

from typing import Any

from factory_contracts import AgentModels, AgentSpec
from factory_core.errors import RegistryError


def _needed(steps: list[dict[str, Any]]) -> list[str]:
    blob = " ".join(str(step.get("goal", "")) for step in steps).lower()
    caps = ["change"]
    if any(token in blob for token in ("api", "health", "endpoint", "http")):
        caps.append("api-design")
    if "test" in blob:
        caps.append("tests")
    return caps


def _coverage(agent: AgentSpec, needed: list[str]) -> float:
    if not needed:
        return 1.0
    have = set(agent.capabilities)
    return len(set(needed) & have) / len(set(needed))


def _bump(version: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    return f"{major}.{minor}.{patch + 1}"


async def assemble_agent(database: Any, steps: list[dict[str, Any]]) -> AgentSpec:
    needed = _needed(steps)
    workers = [
        agent
        for agent in await database.list_agents()
        if agent.id.startswith("agent.worker") and agent.status != "retired"
    ]
    if workers:
        best = max(workers, key=lambda agent: _coverage(agent, needed))
        if _coverage(best, needed) >= 0.9:
            return best
        version = _bump(best.version)
        parent = f"{best.id}@{best.version}"
    else:
        version = "0.1.0"
        parent = None
    spec = AgentSpec(
        id="agent.worker",
        version=version,
        status="draft",
        capabilities=needed,
        lineage={"parent": parent, "reason": "assembled from the plan"} if parent else {},
        models=AgentModels(tier="fast-coding", harness=["claude-code", "codex"]),
    )
    try:
        await database.put_agent(spec)
    except RegistryError:
        return await database.get_agent(spec.id, version)
    return spec

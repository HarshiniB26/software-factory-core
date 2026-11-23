from pathlib import Path

import pytest
from factory_contracts import AgentModels, AgentSpec, SkillSpec
from factory_core import Database, RegistryError


def _agent(version: str) -> AgentSpec:
    return AgentSpec(
        id="agent.backend-api",
        version=version,
        status="active",
        capabilities=["api-design"],
        skills=["superpowers/test-driven-development@example"],
        models=AgentModels(tier="frontier-coding", harness=["claude-code"]),
    )


async def test_agent_versions_are_immutable_and_latest_wins(database: Database) -> None:
    await database.put_agent(_agent("3.1.0"))
    await database.put_agent(_agent("3.2.0"))
    latest = await database.get_agent("agent.backend-api")
    assert latest.version == "3.2.0"
    pinned = await database.get_agent("agent.backend-api", "3.1.0")
    assert pinned.version == "3.1.0"
    with pytest.raises(RegistryError, match="already exists"):
        await database.put_agent(_agent("3.2.0"))
    listed = await database.list_agents("api-design")
    assert [item.version for item in listed] == ["3.2.0"]
    assert await database.list_agents("missing") == []


async def test_skill_pin_round_trip(database: Database) -> None:
    spec = SkillSpec(
        id="superpowers/test-driven-development",
        version="0.1.0",
        source="https://github.com/obra/superpowers",
        license="MIT",
        description="Write a failing test first.",
    )
    await database.put_skill(spec)
    assert (await database.get_skill(spec.id)).description.startswith("Write")


def test_example_agent_file_matches_the_schema() -> None:
    path = Path(__file__).resolve().parents[3] / "registry" / "agents" / "backend-api.yaml"
    text = path.read_text(encoding="utf-8")
    import yaml

    loaded = yaml.safe_load(text)
    spec = AgentSpec.model_validate(loaded)
    assert spec.id == "agent.backend-api"
    assert spec.version == "3.2.0"
    assert spec.status == "active"

from factory_contracts import AgentModels, AgentSpec, AgentTools

from factory_pipeline.registry import agent_profile, cosine, embed, fallback_decision, parse_decision, step_need


def test_embed_is_stable_and_similar_for_the_same_need() -> None:
    left = embed("implementer add an HTTP handler")
    right = embed("implementer add an HTTP handler")
    other = embed("reviewer read the diff only")
    assert cosine(left, right) > 0.99
    assert cosine(left, other) < 1


def test_judge_json_is_accepted_only_when_the_reason_is_present() -> None:
    assert parse_decision('{"decision":"CREATE","reason":"no match"}') == (
        "CREATE",
        "no match",
    )
    assert parse_decision("not json") is None


def test_profile_match_prefers_the_agent_whose_skills_fit_the_step() -> None:
    need = embed(step_need({"role": "implementer", "goal": "add tests for the health handler", "capabilities": ["add or update tests"]}))
    tester = AgentSpec(
        id="agent.implementer",
        version="0.1.0",
        prompt="Write tests first.",
        capabilities=["add or update tests"],
        skills=["superpowers-test-driven-development"],
        tools=AgentTools(allow=["shell"]),
        models=AgentModels(tier="fast-coding", harness=["codex"]),
    )
    writer = AgentSpec(
        id="agent.docs",
        version="0.1.0",
        prompt="Write user facing docs.",
        capabilities=["documentation"],
        skills=["pstack-technical-writing"],
        tools=AgentTools(allow=["read"]),
        models=AgentModels(tier="small", harness=["claude-code"]),
    )
    assert "superpowers-test-driven-development" in agent_profile(tester)
    assert cosine(need, embed(agent_profile(tester))) > cosine(need, embed(agent_profile(writer)))


def test_fallback_creates_when_nothing_is_close() -> None:
    decision, reason = fallback_decision(None, 0)
    assert decision == "CREATE"
    assert reason

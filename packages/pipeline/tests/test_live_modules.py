import asyncio
from types import SimpleNamespace

import httpx
import pytest
from factory_cli.doctor import report
from factory_contracts import ChatMessage, TaskSpec
from factory_eval_replay import ReplayEval
from factory_harnesses.claude import ClaudeHarness
from factory_harnesses.codex import CodexHarness
from factory_model_litellm import LiteLLMModel
from factory_pipeline.evals import promotion_allowed
from factory_skills_git import GitSkillSource


def test_doctor_lists_docker_and_github() -> None:
    names = {name for name, _ok, _detail in report()}
    assert "python" in names
    assert "docker" in names
    assert "git" in names
    assert "auth-mode" in names or "github-app" in names


async def test_heldout_seed_can_promote() -> None:
    scores = await ReplayEval().run("heldout", "seed")
    assert scores.n >= 30
    allowed, reason = promotion_allowed(
        {"n": scores.n, "pass_rate": scores.pass_rate, "cost_per_task_usd": 0.1},
        {"n": scores.n, "pass_rate": scores.pass_rate, "cost_per_task_usd": 0.1},
    )
    assert allowed, reason


async def test_pinned_skills_keep_license_and_sha() -> None:
    source = GitSkillSource()
    items = await source.list()
    assert len(items) >= 11
    for item in items:
        verified = await source.verify(item.ref)
        assert verified.ok
        assert verified.license == "MIT"
        assert "22f0b463e7a5e579904dd6211a520321035526f7" in item.ref or (
            "7a583913eb1b8d1a0ee76753d1a2cf072e7b54f9" in item.ref
        )


async def test_claude_live_runner_maps_usage_and_retries() -> None:
    calls = {"n": 0}

    async def runner(spec: TaskSpec):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("temporary")

        async def generate():
            yield SimpleNamespace(text="working")
            yield SimpleNamespace(
                result="pong",
                total_cost_usd=0.2,
                usage={"input_tokens": 2, "output_tokens": 3},
                is_error=False,
            )

        return generate()

    harness = ClaudeHarness(runner=runner)
    task_id = await harness.start_task(TaskSpec(instruction="ping"))
    events = [event async for event in harness.stream_events(task_id)]
    result = await harness.get_result(task_id)
    usage = await harness.usage(task_id)
    assert calls["n"] == 2
    assert any(event.type == "result" and event.message == "pong" for event in events)
    assert result.status == "ok"
    assert usage.tokens == 5
    assert usage.usd == 0.2


async def test_claude_timeout_and_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FACTORY_HARNESS_TIMEOUT", "1")

    async def runner(spec: TaskSpec):
        async def generate():
            await asyncio.sleep(5)
            yield SimpleNamespace(result="late", is_error=False)

        return generate()

    harness = ClaudeHarness(runner=runner)
    task_id = await harness.start_task(TaskSpec(instruction="slow"))
    events = [event async for event in harness.stream_events(task_id)]
    assert events[-1].type == "error"
    assert "timed out" in events[-1].message

    started = asyncio.Event()

    async def blocking(spec: TaskSpec):
        async def generate():
            started.set()
            await asyncio.sleep(30)
            yield SimpleNamespace(result="nope", is_error=False)

        return generate()

    live = ClaudeHarness(runner=blocking)
    live_id = await live.start_task(TaskSpec(instruction="cancel"))

    async def consume() -> None:
        async for _event in live.stream_events(live_id):
            pass

    task = asyncio.create_task(consume())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert live._tasks[live_id].status == "cancelled"


async def test_codex_live_runner_maps_usage() -> None:
    async def runner(spec: TaskSpec) -> SimpleNamespace:
        return SimpleNamespace(
            final_response="pong",
            usage=SimpleNamespace(total_tokens=4),
            cost_usd=0.05,
        )

    harness = CodexHarness(runner=runner)
    task_id = await harness.start_task(TaskSpec(instruction="ping"))
    events = [event async for event in harness.stream_events(task_id)]
    usage = await harness.usage(task_id)
    assert [event.type for event in events] == ["message", "result"]
    assert usage.tokens == 4
    assert usage.usd == 0.05


async def test_litellm_proxy_records_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FACTORY_LITELLM_URL", "http://litellm.test")
    monkeypatch.setenv("FACTORY_LITELLM_API_KEY", "test-key")
    monkeypatch.delenv("FACTORY_LITELLM_EMBEDDED", raising=False)

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [{"message": {"content": "pong"}}],
                "usage": {"cost": 0.2},
            }

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.calls: list[str] = []

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(
            self, url: str, json: dict[str, object], headers: dict[str, str]
        ) -> FakeResponse:
            assert url == "http://litellm.test/chat/completions"
            assert headers["authorization"] == "Bearer test-key"
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    model = LiteLLMModel()
    messages = [ChatMessage(role="user", content="ping")]
    completion = await model.complete("litellm/fast-coding", messages)
    usage = await model.usage("litellm/fast-coding")
    assert completion.text == "pong"
    assert usage.usd == 0.2


async def test_fixture_harness_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("FACTORY_LITELLM_URL", raising=False)
    monkeypatch.delenv("FACTORY_LITELLM_API_KEY", raising=False)
    claude = ClaudeHarness()
    task_id = await claude.start_task(TaskSpec(instruction="offline"))
    events = [event async for event in claude.stream_events(task_id)]
    assert events[0].type == "started"
    model = LiteLLMModel()
    messages = [ChatMessage(role="user", content="offline")]
    completion = await model.complete("litellm/fast-coding", messages)
    assert completion.text
    assert (await model.usage("litellm/fast-coding")).usd == 0.01

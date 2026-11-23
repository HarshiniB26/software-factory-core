"""One assertion function per module interface."""

import asyncio
from collections.abc import Awaitable
from datetime import UTC, datetime
from uuid import uuid4

from factory_contracts import (
    AuthProvider,
    AuthRequest,
    ChatMessage,
    Clarifier,
    ContractError,
    EvalRunner,
    EventDraft,
    FactoryEvent,
    FactoryRequest,
    GateContext,
    HarnessAdapter,
    IntakeSource,
    ModelProvider,
    Notifier,
    ObservabilityExporter,
    ObservabilityItem,
    Orchestrator,
    Plan,
    Planner,
    PullRequestRef,
    PullRequestSpec,
    QualityGate,
    Question,
    RepoContext,
    SandboxProvider,
    SandboxSpec,
    SecretsProvider,
    SkillSource,
    Spec,
    Storage,
    TaskDAG,
    TaskSpec,
    TaskStep,
    VcsProvider,
)


async def _expect_contract_error(awaitable: Awaitable[object]) -> None:
    try:
        await awaitable
    except ContractError:
        return
    raise AssertionError("expected ContractError")


async def assert_orchestrator_contract(orchestrator: Orchestrator) -> None:
    workflow_id = await orchestrator.start_workflow(
        "NoOpRequestWorkflow", {"request_id": "r"}, "wf-1"
    )
    assert workflow_id == "wf-1"
    await orchestrator.signal(workflow_id, "ping", {"status": "signaled"})
    state = await orchestrator.query(workflow_id, "status")
    assert state["status"] == "signaled"
    schedule_id = await orchestrator.schedule("NoOpRequestWorkflow", "0 * * * *", {})
    assert schedule_id
    await orchestrator.cancel(workflow_id)
    cancelled = await orchestrator.query(workflow_id, "status")
    assert cancelled["status"] == "cancelled"


async def assert_storage_contract(storage: Storage) -> None:
    request_id = uuid4()
    seen: list[FactoryEvent] = []

    async def consume() -> None:
        async for event in storage.subscribe(request_id):
            seen.append(event)
            return

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    written = await storage.append(
        EventDraft(request_id=request_id, type="request.created", payload={"n": 1})
    )
    await asyncio.wait_for(task, timeout=2)
    assert seen[0].id == written.id
    assert (await storage.read(request_id))[0].seq == 1
    await storage.put_state("k", {"a": 1})
    assert await storage.get_state("k") == {"a": 1}
    assert await storage.get_state("missing") is None
    key = await storage.put_blob("notes/a.txt", b"hello", "text/plain")
    assert await storage.get_blob(key) == b"hello"
    await _expect_contract_error(storage.get_blob("missing"))


async def assert_intake_contract(intake: IntakeSource) -> None:
    thread_id = await intake.open_thread("octocat", "octocat/demo")
    assert thread_id
    draft = await intake.receive("add healthcheck", [])
    assert "healthcheck" in draft.body
    assert draft.kind == "new"
    follow = await intake.follow_up(thread_id, "also add tests")
    assert follow.kind in {"revise", "child"}
    await intake.ack(thread_id, uuid4())


async def assert_notifier_contract(notifier: Notifier) -> None:
    await notifier.ask(
        "thread-1",
        [Question(text="Which db?", options=["postgres", "sqlite"], default="postgres")],
    )
    plan = Plan(
        id=uuid4(),
        request_id=uuid4(),
        summary="add health",
        dag=TaskDAG(steps=[TaskStep(id="step-1", goal="add health")]),
    )
    approval = await notifier.show_plan(plan)
    assert approval.status in {"pending", "approved", "rejected"}
    await notifier.progress(
        FactoryEvent(
            id=uuid4(),
            request_id=plan.request_id,
            seq=1,
            type="request.created",
            payload={},
            created_at=datetime.now(UTC),
        )
    )
    await notifier.done(
        [PullRequestRef(repo="octocat/demo", number=1, url="https://example.test/1")]
    )
    reply = await notifier.on_reply("thread-1")
    assert reply is None or isinstance(reply, str)


async def assert_clarifier_contract(clarifier: Clarifier) -> None:
    request = FactoryRequest(
        id=uuid4(),
        title="Add health",
        body="Add GET /health",
        requester="octocat",
        status="created",
        created_at=datetime.now(UTC),
    )
    result = await clarifier.assess(request, RepoContext(repo="octocat/demo"))
    assert result.status in {"clear", "questions", "assumptions"}


async def assert_planner_contract(planner: Planner) -> None:
    dag = await planner.plan(
        Spec(request_id=uuid4(), summary="add healthcheck", checks=["curl /health"])
    )
    assert dag.steps
    assert dag.steps[0].goal


async def assert_harness_contract(adapter: HarnessAdapter) -> None:
    assert adapter.capabilities().streaming
    task_id = await adapter.start_task(TaskSpec(instruction="add a test"))
    stream = adapter.stream_events(task_id)
    first = await asyncio.wait_for(stream.__anext__(), timeout=2)
    assert first.type
    await stream.aclose()
    await adapter.send_message(task_id, "continue")
    assert (await adapter.get_result(task_id)).status == "ok"
    assert (await adapter.usage(task_id)).tokens >= 0
    await adapter.cancel(task_id)
    assert (await adapter.get_result(task_id)).status == "cancelled"


async def assert_model_contract(models: ModelProvider) -> None:
    choice = await models.route("coder", "implement handler")
    assert choice.model
    completion = await models.complete(choice.model, [ChatMessage(role="user", content="hi")])
    assert completion.text
    budget = await models.budget("run-1")
    assert budget.limit_usd >= budget.spent_usd
    assert (await models.usage("run-1")).tokens >= 0


async def assert_sandbox_contract(provider: SandboxProvider) -> None:
    handle = await provider.create(SandboxSpec())
    assert handle.id
    ok = await provider.exec(handle.id, ["echo", "hi"])
    assert ok.exit_code == 0
    assert "hi" in ok.stdout
    denied = await provider.exec(handle.id, ["curl", "https://evil.example"])
    assert denied.exit_code != 0
    sha = await provider.fetch_branch(handle.id, "main")
    assert len(sha) >= 7
    snapshot = await provider.snapshot(handle.id)
    assert snapshot is None or isinstance(snapshot, str)
    await provider.pause(handle.id)
    usage = await provider.usage(handle.id)
    assert usage.seconds >= 0
    await provider.destroy(handle.id)
    await _expect_contract_error(provider.exec(handle.id, ["echo", "hi"]))


async def assert_vcs_contract(vcs: VcsProvider) -> None:
    await vcs.connect("octocat")
    created = await vcs.create_repo("demo")
    assert created is not None
    repos = await vcs.list_repos("octocat")
    assert any(repo.name == "demo" for repo in repos)
    repo = created.full_name
    await vcs.push_branch(repo, "factory/req/step", "abc123")
    pull = await vcs.open_pr(
        repo,
        PullRequestSpec(title="Add health", body="body", head="factory/req/step", base="main"),
    )
    assert pull.number >= 1
    updated = await vcs.update_pr(
        repo,
        pull.number,
        PullRequestSpec(title="Add health check", head="factory/req/step", base="main"),
    )
    assert "health" in updated.title
    await vcs.comment(repo, pull.number, "hello")
    assert await vcs.checks(repo, "abc123")
    event = await vcs.parse_webhook({"x-factory-event": "ping"}, b"{}")
    assert event.name == "ping"
    await _expect_contract_error(vcs.parse_webhook({}, b"{}"))


async def assert_gate_contract(gate: QualityGate) -> None:
    assert isinstance(gate.applies_to("octocat/demo", ""), bool)
    result = await gate.run("sbx", GateContext(repo="octocat/demo", diff=""))
    assert result.verdict in {"pass", "fail"}


async def assert_skill_contract(source: SkillSource) -> None:
    items = await source.list()
    assert items
    bundle = await source.fetch(items[0].ref)
    assert bundle.content
    verified = await source.verify(items[0].ref)
    assert verified.ok
    assert verified.license


async def assert_eval_contract(runner: EvalRunner) -> None:
    scores = await runner.run("backend-api", "1.0.0")
    assert scores.n >= 0
    compared = await runner.compare("1.0.0", "1.1.0")
    assert compared.a == "1.0.0"
    assert compared.b == "1.1.0"


async def assert_observability_contract(exporter: ObservabilityExporter) -> None:
    await exporter.export(
        ObservabilityItem(kind="event", name="request.created", attributes={"n": 1})
    )


async def assert_auth_contract(auth: AuthProvider) -> None:
    principal = await auth.authenticate(AuthRequest(headers={"authorization": "Bearer test"}))
    assert principal.id
    assert principal.roles
    await _expect_contract_error(auth.authenticate(AuthRequest(headers={})))


async def assert_secrets_contract(secrets: SecretsProvider) -> None:
    value = await secrets.get("factory/example")
    assert value
    token = await secrets.issue_short_lived("repo:demo")
    assert "repo:demo" in token
    await _expect_contract_error(secrets.get("missing/nope"))

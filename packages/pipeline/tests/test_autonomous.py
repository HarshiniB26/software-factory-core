"""Live orchestration tests use real Git workspaces and controlled T3 responses."""

import asyncio
import json
import shutil
import sys
from pathlib import Path

import pytest
from factory_contracts import ContractError, HarnessEvent, HarnessResult, RequestCreate, TaskSpec
from factory_core import connect, set_database
from factory_harnesses.t3 import T3Harness
from factory_pipeline import autonomous
from factory_pipeline.service import tick
from factory_pipeline.skills import instructions
from factory_pipeline.workspace import command, git, prepare
from factory_skills_git import GitSkillSource


async def repository(root: Path) -> Path:
    await asyncio.to_thread(root.mkdir)
    await command(["git", "init", "-b", "main"], root)
    (root / "app.py").write_text("VALUE = 1\n")
    await git(root, "add", "app.py")
    await git(root, "-c", "user.name=Test", "-c", "user.email=test@local", "commit", "-m", "init")
    return root


async def test_prepare_selected_branch_and_fail_on_missing_branch(tmp_path):
    repo = await repository(tmp_path / "source")
    await git(repo, "checkout", "-b", "develop")
    (repo / "app.py").write_text("VALUE = 2\n")
    # A branch can be selected even before a second commit; cloning must preserve it.
    clone = await prepare(str(repo), "develop", tmp_path / "clone", None)
    assert await git(clone, "branch", "--show-current") == "develop"
    with pytest.raises(ContractError):
        await prepare(str(repo), "missing", tmp_path / "bad", None)
    with pytest.raises(ContractError, match="already exists"):
        await prepare(str(repo), "main", tmp_path / "clone", None)


async def test_skills_are_delivered_and_wrong_pin_or_tampering_rejected(tmp_path):
    source = GitSkillSource()
    text, receipts = await instructions(source, "discover")
    assert "Root Cause Investigation" in text
    assert "root-cause-tracing.md" in text
    assert len(receipts) == 2 and all(len(item["sha256"]) == 64 for item in receipts)
    ref = receipts[0]["ref"]
    with pytest.raises(ContractError, match="unpinned"):
        await source.fetch(ref.split("@")[0] + "@wrong")
    root = tmp_path / "pins"
    shutil.copytree(Path("registry/skills/pins"), root)
    target = root / "superpowers-systematic-debugging/SKILL.md"
    target.write_text(target.read_text() + "\nInjected instructions\n")
    with pytest.raises(ContractError, match="integrity"):
        await GitSkillSource(root).fetch(ref)


@pytest.mark.parametrize("text", ["looks good", '{"steps": []}', "```json\n{}\n```"])
def test_invalid_plans_never_fall_back(text):
    with pytest.raises(ContractError, match="no fallback"):
        autonomous.structured(text, autonomous.GroundedPlan)


async def test_live_default_cannot_report_fake_success(tmp_path, monkeypatch):
    monkeypatch.setenv("FACTORY_EXECUTION_MODE", "live")
    monkeypatch.delenv("FACTORY_T3_PROVIDER", raising=False)
    monkeypatch.delenv("FACTORY_T3_MODEL", raising=False)
    database = await connect(f"sqlite+aiosqlite:///{tmp_path}/db", blob_root=tmp_path / "blobs")
    set_database(database)
    request = await database.create_request(
        RequestCreate(title="Fix", body="Fix it", target="org/repo")
    )
    result = await tick(request.id)
    assert result["status"] == "failed"
    assert "FACTORY_T3_PROVIDER" in result["detail"]
    assert not result.get("prs")
    await database.dispose()


class ControlledSession:
    """Contract fixture: the production adapter is tested separately below."""

    def __init__(self, dirty_discovery=False, failed=False):
        self.prompts = []
        self.workspace = ""
        self.response = ""
        self.failed = failed
        self.dirty_discovery = dirty_discovery
        self.starts = 0

    async def start_task(self, task):
        self.starts += 1
        self.workspace = task.repo
        await git(self.workspace, "checkout", "-b", task.branch)
        await self.respond(task.instruction)
        return "persistent-thread"

    async def send_message(self, task_id, message):
        assert task_id == "persistent-thread"
        await self.respond(message)

    async def respond(self, message):
        self.prompts.append(message)
        if "READ ONLY: inspect" in message:
            if self.dirty_discovery:
                (Path(self.workspace) / "app.py").write_text("unauthorized edit\n")
            self.response = json.dumps(
                {
                    "project_type": "brownfield",
                    "findings": "app.py defines VALUE",
                    "baseline_commands": [
                        [sys.executable, "-B", "-c", "from app import VALUE; assert VALUE == 1"]
                    ],
                    "files_read": ["app.py"],
                    "questions": ["Should VALUE become 2?"],
                }
            )
        elif "READ ONLY: create a plan" in message:
            self.response = json.dumps(
                {
                    "summary": "Update existing constant",
                    "acceptance_criteria": ["VALUE equals 2"],
                    "steps": ["Update VALUE"],
                    "files": ["app.py"],
                    "risk": "low",
                    "questions": [],
                    "verification": [
                        [sys.executable, "-B", "-c", "from app import VALUE; assert VALUE == 2"]
                    ],
                }
            )
        elif "Implement the approved plan" in message:
            (Path(self.workspace) / "app.py").write_text("VALUE = 2\n")
            self.response = "Implemented"
        else:
            self.response = '{"verdict":"pass","findings":"Inspected the full diff"}'

    async def stream_events(self, task_id):
        yield HarnessEvent(type="result", message=self.response)

    async def get_result(self, task_id):
        return HarnessResult(
            status="failed" if self.failed else "ok",
            summary=self.response,
            workspace=self.workspace,
        )


async def setup_live(tmp_path, monkeypatch, session):
    monkeypatch.setenv("FACTORY_EXECUTION_MODE", "live")
    monkeypatch.setenv("FACTORY_T3_PROVIDER", "configured-provider")
    monkeypatch.setenv("FACTORY_T3_MODEL", "configured-model")
    monkeypatch.setenv("FACTORY_WORKSPACE_ROOT", str(tmp_path / "runs"))
    source = await repository(tmp_path / "source")
    database = await connect(f"sqlite+aiosqlite:///{tmp_path}/db", blob_root=tmp_path / "blobs")
    set_database(database)
    request = await database.create_request(
        RequestCreate(title="Change VALUE", body="Set VALUE to 2", target=str(source))
    )
    await database.put_state(
        f"run:{request.id}", {"overrides": {"flags": {"plan_approval": "always"}}}
    )

    async def selected(name):
        return session if name == "harness-t3" else GitSkillSource()

    monkeypatch.setattr(autonomous, "selected", selected)
    return database, request


async def test_single_session_inspects_then_pauses_then_implements_and_verifies(
    tmp_path, monkeypatch
):
    session = ControlledSession()
    database, request = await setup_live(tmp_path, monkeypatch, session)
    assert (await tick(request.id))["status"] == "running"  # checkout
    assert (await tick(request.id))["status"] == "parked"  # inspect before plan
    assert len(session.prompts) == 1
    assert (await tick(request.id))["status"] == "parked"  # no guessed answer
    planned = await tick(request.id, {"answer": "Yes, use 2"})
    assert planned["status"] == "awaiting_approval"
    assert "Yes, use 2" in session.prompts[-1]
    assert (await tick(request.id))["status"] == "awaiting_approval"
    assert (await tick(request.id, {"decision": "approve"}))["status"] == "running"
    assert (await tick(request.id))["status"] == "running"  # review
    assert (await tick(request.id))["status"] == "running"  # verify
    state = await database.get_state(f"run:{request.id}")
    assert state["verified_sha"] == await git(state["workspace"], "rev-parse", "HEAD")
    assert state["verification"][0]["exit_code"] == 0
    assert session.starts == 1
    assert "Write" in session.prompts[2]  # skill contents reach implementation
    assert not (Path(state["workspace"]) / "FACTORY_STEP.md").exists()
    # Local-only runs cannot invent a GitHub URL or report PR completion.
    assert (await tick(request.id))["status"] == "failed"
    assert not (await database.get_state(f"run:{request.id}")).get("prs")
    await database.dispose()


@pytest.mark.parametrize("dirty,failed", [(True, False), (False, True)])
async def test_discovery_edits_and_failed_harness_stop_before_plan(
    tmp_path, monkeypatch, dirty, failed
):
    session = ControlledSession(dirty_discovery=dirty, failed=failed)
    database, request = await setup_live(tmp_path, monkeypatch, session)
    await tick(request.id)
    result = await tick(request.id)
    assert result["status"] == "failed"
    assert len(session.prompts) == 1
    await database.dispose()


async def test_ambiguous_operation_never_launches_another_session(tmp_path, monkeypatch):
    session = ControlledSession()
    database, request = await setup_live(tmp_path, monkeypatch, session)
    await database.put_state(f"run:{request.id}", {"pending_operation": "discover"})
    result = await tick(request.id)
    assert result["status"] == "failed" and "uncertain" in result["detail"]
    assert session.starts == 0
    await database.dispose()


async def test_t3_cli_passes_provider_model_workspace_and_does_not_accept_old_message(tmp_path):
    harness = T3Harness()
    calls = []

    async def cli(args, message=None):
        calls.append((args, message))
        if args[:2] == ["thread", "start"]:
            return '{"threadId":"thread-1"}'
        if args[:2] == ["thread", "show"]:
            return json.dumps(
                {
                    "thread": {
                        "activeRunId": None,
                        "archived": False,
                        "worktreePath": str(tmp_path),
                    },
                    "messages": [{"role": "assistant", "text": "result"}],
                }
            )
        return ""

    harness._cli = cli

    async def catalog():
        return [
            {"id": "claude-instance", "enabled": True, "models": ["chosen-model"]},
            {"id": "configured", "enabled": True, "models": ["configured"]},
        ]

    harness.catalog = catalog
    task_id = await harness.start_task(
        TaskSpec(
            instruction="inspect",
            repo=str(tmp_path),
            branch="factory/test",
            provider="claude-instance",
            model="chosen-model",
        )
    )
    args = next(args for args, _ in calls if args[:2] == ["thread", "start"])
    assert args[args.index("--provider") + 1] == "claude-instance"
    assert args[args.index("--model") + 1] == "chosen-model"
    assert any(message == "inspect" for _, message in calls)
    assert calls[0][0][:2] == ["project", "add"]
    assert task_id == "thread-1"
    assert (await harness.get_result(task_id)).workspace == str(tmp_path)
    await harness.send_message(task_id, "plan")
    assert harness._baseline[task_id] == "result"


async def test_t3_unknown_launch_response_fails_for_reconciliation(tmp_path):
    harness = T3Harness()

    async def cli(args, message=None):
        return "not JSON"

    harness._cli = cli

    async def catalog():
        return [
            {"id": "claude-instance", "enabled": True, "models": ["chosen-model"]},
            {"id": "configured", "enabled": True, "models": ["configured"]},
        ]

    harness.catalog = catalog
    with pytest.raises(ContractError, match="reconcile"):
        await harness.start_task(
            TaskSpec(
                instruction="inspect",
                repo=str(tmp_path),
                branch="factory/test",
                provider="configured",
                model="configured",
            )
        )


async def test_live_run_view_never_fabricates_diff_scanners_or_agents(tmp_path, monkeypatch):
    from factory_api.main import create_app
    from factory_fakes.orchestrator import FakeOrchestrator
    from httpx import ASGITransport, AsyncClient

    monkeypatch.setenv("FACTORY_EXECUTION_MODE", "live")
    database = await connect(f"sqlite+aiosqlite:///{tmp_path}/db", blob_root=tmp_path / "blobs")
    created = await database.create_request(RequestCreate(title="Fix", body="Fix checkout"))
    await database.put_state(f"run:{created.id}", {"execution_mode": "live"})
    app = create_app(database, FakeOrchestrator())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/requests/{created.id}/view")
    assert response.status_code == 200
    view = response.json()
    assert view["execution_mode"] == "live"
    assert view["diff"] == "" and view["diff_kind"] == "unavailable"
    assert view["gates"] == [] and view["crew"] == [] and view["logs"] == []
    assert view["usage_available"] is False
    await database.dispose()


@pytest.mark.parametrize("matching_head", [True, False])
async def test_publish_uses_real_github_response_and_verified_head(
    tmp_path, monkeypatch, matching_head
):
    import httpx

    repo = await repository(tmp_path / "source")
    sha = await git(repo, "rev-parse", "HEAD")
    database = await connect(f"sqlite+aiosqlite:///{tmp_path}/db", blob_root=tmp_path / "blobs")
    request = await database.create_request(RequestCreate(title="Fix", body="Fix it"))
    state = {
        "target": "org/repo",
        "workspace": str(repo),
        "verified_sha": sha,
        "branch": "factory/test",
        "base": "develop",
        "grounded_plan": {"summary": "Fix"},
        "review": {"findings": "Reviewed"},
        "verification": [{"argv": ["pytest"]}],
    }
    pushes = []
    actual_git = autonomous.git

    async def intercepted_git(workspace, *args, token=None):
        if args[0] == "push":
            pushes.append(args)
            assert token == "short-lived-token"
            return ""
        return await actual_git(workspace, *args)

    async def installation(*args):
        return "short-lived-token"

    monkeypatch.setattr(autonomous, "git", intercepted_git)
    monkeypatch.setattr(autonomous, "installation", installation)
    requests = []

    def respond(incoming):
        requests.append(incoming)
        if incoming.method == "GET":
            return httpx.Response(200, json=[])
        body = json.loads(incoming.content)
        assert body["base"] == "develop" and body["head"] == "factory/test"
        assert sha in body["body"]
        return httpx.Response(
            201,
            json={
                "number": 42,
                "html_url": "https://github.com/org/repo/pull/42",
                "head": {"sha": sha if matching_head else "wrong"},
            },
        )

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    if matching_head:
        await autonomous.publish(database, request, state)
        assert state["prs"][0]["number"] == 42
        assert "pending_operation" not in state
    else:
        with pytest.raises(ContractError, match="verified commit"):
            await autonomous.publish(database, request, state)
        assert not state.get("prs")
    assert pushes[0][-1] == f"{sha}:refs/heads/factory/test"
    assert len(requests) == 2
    await database.dispose()


async def test_t3_catalog_uses_configured_instances_and_current_models(tmp_path, monkeypatch):
    home = tmp_path / "userdata"
    await asyncio.to_thread(home.mkdir)
    (home / "settings.json").write_text(
        json.dumps(
            {
                "providerInstances": {
                    "team-claude": {
                        "driver": "claudeAgent",
                        "displayName": "Team",
                        "enabled": True,
                    },
                    "disabled": {"driver": "codex", "enabled": False},
                }
            }
        )
    )
    (home / "model-manifest.json").write_text(
        json.dumps(
            {
                "manifest": {
                    "currentModels": {"claudeAgent": ["available-model"], "codex": ["other-model"]}
                }
            }
        )
    )
    monkeypatch.setenv("T3CODE_HOME", str(tmp_path))
    harness = T3Harness()
    catalog = await harness.catalog()
    assert catalog[0]["id"] == "team-claude"
    assert catalog[0]["models"] == ["available-model"]
    with pytest.raises(ContractError, match="unavailable"):
        await harness.start_task(
            TaskSpec(
                instruction="inspect",
                repo=str(tmp_path),
                branch="factory/test",
                provider="disabled",
                model="other-model",
            )
        )


def test_execution_mode_defaults_to_live(monkeypatch):
    from factory_core import Settings

    monkeypatch.delenv("FACTORY_EXECUTION_MODE")
    assert Settings().execution_mode == "live"


async def test_failing_verification_repairs_then_stops_without_publication(tmp_path, monkeypatch):
    session = ControlledSession()
    database, request = await setup_live(tmp_path, monkeypatch, session)
    await tick(request.id)
    await tick(request.id)
    await tick(request.id, {"answer": "Yes"})
    await tick(request.id, {"decision": "approve"})
    await tick(request.id)
    state = await database.get_state(f"run:{request.id}")
    state["grounded_plan"]["verification"] = [[sys.executable, "-c", "raise SystemExit(1)"]]
    await database.put_state(f"run:{request.id}", state)
    assert (await tick(request.id))["status"] == "running"
    state = await database.get_state(f"run:{request.id}")
    assert state["live_stage"] == "implement"
    assert state["grounded_plan"]["verification_findings"]["failed_command"]
    state["live_stage"] = "verify"
    state["fix_round"] = 2
    await database.put_state(f"run:{request.id}", state)
    assert (await tick(request.id))["status"] == "failed"
    assert not (await database.get_state(f"run:{request.id}")).get("prs")
    await database.dispose()


async def test_expired_clarification_never_invents_an_answer(tmp_path, monkeypatch):
    session = ControlledSession()
    database, request = await setup_live(tmp_path, monkeypatch, session)
    await tick(request.id)
    await tick(request.id)
    result = await tick(request.id, {"timeout": "1"})
    assert result["status"] == "failed" and "no answer was assumed" in result["detail"]
    assert len(session.prompts) == 1
    await database.dispose()


async def test_clear_routine_work_proceeds_without_plan_approval(tmp_path, monkeypatch):
    session = ControlledSession()
    database, request = await setup_live(tmp_path, monkeypatch, session)
    await database.put_state(f"run:{request.id}", {})
    await tick(request.id)
    await tick(request.id)
    result = await tick(request.id, {"answer": "Yes, use 2"})
    assert result["status"] == "running"
    assert (await database.get_state(f"run:{request.id}"))["live_stage"] == "implement"
    await database.dispose()

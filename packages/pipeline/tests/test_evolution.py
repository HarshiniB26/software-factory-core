import asyncio
import time
from datetime import timedelta

import pytest
from factory_contracts import ContractError, RequestCreate
from factory_core import connect, set_database
from factory_core.db import StateRow, utcnow
from factory_pipeline.learning import Proposal, enhancement, promote, propose
from factory_pipeline.profiles import validate_plan
from factory_pipeline.supervision import supervised, watchdog
from sqlalchemy import update


@pytest.fixture
async def store(tmp_path):
    database = await connect(
        f"sqlite+aiosqlite:///{tmp_path}/factory.db", blob_root=tmp_path / "blobs"
    )
    set_database(database)
    yield database
    await database.dispose()


async def test_atomic_lease_and_stale_owner_fencing(store):
    attempts = await asyncio.gather(*(store.acquire_lease("lease:test", str(i)) for i in range(5)))
    assert sum(attempts) == 1
    winner = str(attempts.index(True))
    assert await store.renew_lease("lease:test", winner)
    assert not await store.renew_lease("lease:test", "stranger")
    async with store.session() as session, session.begin():
        await session.execute(
            update(StateRow)
            .where(StateRow.key == "lease:test")
            .values(updated_at=utcnow() - timedelta(seconds=120))
        )
    assert await store.acquire_lease("lease:test", "replacement")
    with pytest.raises(ContractError, match="stale state"):
        await store.put_fenced_state("run:test", {"bad": True}, "lease:test", winner)
    await store.put_fenced_state("run:test", {"good": True}, "lease:test", "replacement")
    assert (await store.get_state("run:test"))["good"]


async def test_duplicate_worker_does_not_execute_operation(store):
    created = await store.create_request(RequestCreate(title="Test", body="Test"))
    assert await store.acquire_lease(f"lease:run:{created.id}", "existing")
    called = False

    async def operation():
        nonlocal called
        called = True

    assert (await supervised(store, created.id, operation))["status"] == "running"
    assert not called


async def test_watchdog_deduplicates_alerts_and_ignores_waiting_for_humans(store):
    created = await store.create_request(RequestCreate(title="Stale", body="Test"))
    await store.put_state(
        f"run:{created.id}", {"execution_mode": "live", "live_stage": "implement"}
    )
    await store.update_status(created.id, "running")
    await store.put_state(f"heartbeat:run:{created.id}", {"at": time.time() - 1000})
    assert len(await watchdog(store)) == 1
    assert len(await watchdog(store)) == 1
    assert (
        len([event for event in await store.read(created.id) if event.type == "monitor.alert"]) == 1
    )
    await store.update_status(created.id, "awaiting_approval")
    assert await watchdog(store) == []


async def test_candidate_is_immutable_and_bound_to_content(store):
    candidate = Proposal(
        reason="Observed missed baseline",
        instructions="Inspect existing tests first.",
        evidence=["run baseline failed"],
    )
    cid = await propose(store, "run-1", "brownfield", candidate)
    assert cid == await propose(store, "run-1", "brownfield", candidate)
    assert (await enhancement(store, "brownfield", cid))["instructions"] == candidate.instructions
    altered = await store.get_state(f"learning:candidate:{cid}")
    altered["instructions"] = "tampered"
    await store.put_state(f"learning:candidate:{cid}", altered)
    with pytest.raises(ContractError, match="integrity"):
        await enhancement(store, "brownfield", cid)


async def evaluated_candidate(store, *, n=30, failure=False, baseline_passes=False):
    cid = await propose(
        store,
        "run",
        "brownfield",
        Proposal(
            reason="Improve tests",
            instructions="Check the existing test runner.",
            evidence=["Missing runner found"],
        ),
    )
    candidate = await store.get_state(f"learning:candidate:{cid}")
    results = [
        {
            "case": str(i),
            "kind": "security" if i < 3 else "recovery" if i < 6 else "functional",
            "variant": variant,
            "verdict": "fail"
            if (
                (variant == "baseline" and not baseline_passes and i == 0)
                or (variant == "candidate" and failure and i == 0)
            )
            else "pass",
            "active_seconds": 1,
        }
        for i in range(n)
        for variant in ("baseline", "candidate")
    ]
    await store.insert_state(
        "learning:evaluation:measured",
        {
            "candidate_id": cid,
            "candidate_hash": candidate["hash"],
            "baseline_id": None,
            "results": results,
        },
    )
    return cid


@pytest.mark.parametrize(
    "n,failure,baseline_passes", [(2, False, False), (30, True, False), (30, False, True)]
)
async def test_promotion_rejects_weak_regressed_or_unimproved_candidates(
    store, n, failure, baseline_passes
):
    cid = await evaluated_candidate(store, n=n, failure=failure, baseline_passes=baseline_passes)
    with pytest.raises(ContractError):
        await promote(store, cid, "measured", "approver")
    assert not await store.get_state("learning:active:brownfield")


async def test_promotion_requires_measured_evidence_and_preserves_parent(store):
    cid = await evaluated_candidate(store)
    with pytest.raises(ContractError, match="matching measured"):
        await promote(store, cid, "client-invented-score", "approver")
    result = await promote(store, cid, "measured", "approver")
    assert result["candidate_id"] == cid
    assert result["approved_by"] == "approver"
    with pytest.raises(ContractError, match="stale"):
        await promote(store, cid, "measured", "approver")


def test_modernization_plan_cannot_omit_preservation_and_rollback():
    with pytest.raises(ContractError, match="preserve"):
        validate_plan(
            {"project_type": "modernization"}, {"acceptance_criteria": ["Behavior preserved"]}
        )


async def test_human_wait_does_not_consume_active_execution_budget(store):
    from factory_pipeline.autonomous import advance

    request = await store.create_request(RequestCreate(title="Wait", body="Test"))
    state = {
        "live_stage": "questions",
        "questions": [{"text": "Which behavior?"}],
        "deadline_at": time.time() - 100000,
        "active_seconds": 2,
    }
    result = await advance(store, request, state, {})
    assert result["status"] == "parked"
    assert state["active_seconds"] < 3
    assert state["deadline_at"] > time.time()


async def test_greenfield_bootstrap_is_explicit_and_brownfield_never_invents_code(tmp_path):
    from factory_pipeline.workspace import command, git, prepare

    origin = tmp_path / "empty.git"
    await command(["git", "init", "--bare", str(origin)])
    with pytest.raises(ContractError):
        await prepare(str(origin), "main", tmp_path / "brownfield", None)
    workspace = await prepare(str(origin), "main", tmp_path / "greenfield", None, bootstrap=True)
    assert await git(workspace, "branch", "--show-current") == "main"
    assert await git(workspace, "ls-files") == "README.md"


async def test_recovery_proves_instruction_identity_before_resuming():
    from factory_harnesses.t3 import T3Harness

    harness = T3Harness()

    async def show(_task):
        return {
            "thread": {"activeRunId": None},
            "messages": [
                {"role": "user", "text": "factory-operation:known\ninspect"},
                {"role": "assistant", "text": "new response"},
            ],
        }

    harness._show = show
    with pytest.raises(ContractError, match="Cannot prove"):
        await harness.recover_operation("thread", "factory-operation:other", "previous response")
    await harness.recover_operation("thread", "factory-operation:known", "previous response")
    assert harness._baseline["thread"] == "previous response"


async def test_compare_and_swap_does_not_overwrite_concurrent_activation(store):
    assert await store.compare_state("active", None, {"version": 1})
    assert not await store.compare_state("active", None, {"version": 2})
    assert await store.compare_state("active", {"version": 1}, {"version": 2})
    assert not await store.compare_state("active", {"version": 1}, {"version": 3})
    assert await store.get_state("active") == {"version": 2}


async def test_promotion_requires_security_and_recovery_coverage(store):
    cid = await evaluated_candidate(store)
    result = await store.get_state("learning:evaluation:measured")
    for row in result["results"]:
        row["kind"] = "functional"
    await store.put_state("learning:evaluation:measured", result)
    with pytest.raises(ContractError, match="security"):
        await promote(store, cid, "measured", "approver")


@pytest.mark.parametrize(
    "conclusion,expected", [("success", "passed"), ("failure", "failed"), (None, "pending")]
)
async def test_ci_uses_actual_check_conclusions(conclusion, expected):
    import httpx
    from factory_pipeline.ci import check_snapshot

    def respond(request):
        if request.url.path.endswith("check-runs"):
            return httpx.Response(
                200,
                json={
                    "total_count": 1,
                    "check_runs": [
                        {
                            "name": "unit tests",
                            "status": "in_progress" if conclusion is None else "completed",
                            "conclusion": conclusion,
                        }
                    ],
                },
            )
        return httpx.Response(200, json={"statuses": []})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), base_url="https://api.github.com"
    ) as client:
        report = await check_snapshot(client, "org/repo", "verified-sha")
    assert report["status"] == expected
    assert report["sha"] == "verified-sha"


async def test_read_only_snapshot_detects_new_file_content_changes(tmp_path):
    from factory_pipeline.workspace import command, git, revision

    await command(["git", "init", "-b", "main", str(tmp_path)])
    (tmp_path / "README.md").write_text("# Test\n")
    await git(tmp_path, "add", "README.md")
    await git(
        tmp_path, "-c", "user.name=Test", "-c", "user.email=test@local", "commit", "-m", "init"
    )
    (tmp_path / "new.py").write_text("before\n")
    before = await revision(str(tmp_path))
    (tmp_path / "new.py").write_text("after\n")
    assert await revision(str(tmp_path)) != before


async def test_verification_does_not_inherit_control_plane_secrets(monkeypatch):
    import sys

    from factory_pipeline.workspace import command

    monkeypatch.setenv("FACTORY_GITHUB_APP_PRIVATE_KEY", "not-for-child-processes")
    assert (
        await command(
            [
                sys.executable,
                "-B",
                "-c",
                "import os; print(os.getenv('FACTORY_GITHUB_APP_PRIVATE_KEY'))",
            ]
        )
        == "None"
    )


async def test_verification_evidence_includes_stderr_test_reports():
    import sys

    from factory_pipeline.workspace import command

    output = await command(
        [sys.executable, "-B", "-c", "import sys; print('1 test passed', file=sys.stderr)"],
        include_stderr=True,
    )
    assert output == "1 test passed"


async def test_stale_worker_cannot_change_request_status(store):
    created = await store.create_request(RequestCreate(title="Fenced", body="Test"))
    await store.acquire_lease("lease:status", "current")
    with pytest.raises(ContractError, match="stale status"):
        await store.fenced_update_status(created.id, "failed", "lease:status", "old")
    assert (await store.get_request(created.id)).status == "created"

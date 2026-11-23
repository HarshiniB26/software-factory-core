from factory_contracts import RequestCreate
from factory_core import connect, set_database
from factory_pipeline.evals import promotion_allowed
from factory_pipeline.merge import merge_preview
from factory_pipeline.risk import approval_needed, score_risk
from factory_pipeline.schedule import schedule
from factory_pipeline.service import classify_follow_up, tick
from factory_vcs_github import APP_PERMISSIONS, GitHubVcs


def test_scheduler_caps_and_isolates_migrations() -> None:
    steps = [
        {"id": "api", "goal": "add endpoint", "touch": ["src/api/"], "depends_on": []},
        {"id": "tests", "goal": "add test", "touch": ["tests/"], "depends_on": []},
        {"id": "ui", "goal": "add page", "touch": ["src/web/"], "depends_on": []},
        {"id": "docs", "goal": "add notes", "touch": ["docs/"], "depends_on": []},
        {"id": "mig", "goal": "add migration", "touch": ["migrations/"], "depends_on": []},
    ]
    waves = schedule(steps, cap=3)
    assert all(len(wave) <= 3 for wave in waves)
    assert any(len(wave) == 1 and wave[0]["id"] == "mig" for wave in waves)


def test_merge_preview_reports_conflicts() -> None:
    merged, conflicts = merge_preview(
        {"a.txt": "base"},
        {"a.txt": "left"},
        {"a.txt": "right"},
    )
    assert conflicts and conflicts[0].path == "a.txt"
    assert "left" in merged["a.txt"]


def test_risk_and_approval() -> None:
    score, level = score_risk([{"goal": "change auth migration", "touch": ["migrations/"]}])
    assert level == "high"
    assert score >= 60
    assert approval_needed("high_risk", "high")
    assert not approval_needed("high_risk", "low")
    assert not approval_needed("never", "high")


def test_promotion_gate() -> None:
    ok, _reason = promotion_allowed(
        {"n": 30, "pass_rate": 0.8, "cost_per_task_usd": 1.0},
        {"n": 30, "pass_rate": 0.8, "cost_per_task_usd": 1.0},
    )
    assert ok
    blocked, reason = promotion_allowed(
        {"n": 30, "pass_rate": 0.9, "cost_per_task_usd": 2.0},
        {"n": 30, "pass_rate": 0.8, "cost_per_task_usd": 1.0},
    )
    assert not blocked
    assert "cost" in reason


def test_github_permissions_never_include_merge() -> None:
    assert "merge" not in APP_PERMISSIONS
    assert APP_PERMISSIONS["contents"] == "write"
    assert not hasattr(GitHubVcs, "merge")


def test_follow_up_classifier() -> None:
    assert classify_follow_up("also add tests") == "child"
    assert classify_follow_up("change the copy") == "revise"


async def test_clear_request_opens_a_pull_request(tmp_path) -> None:
    database = await connect(
        f"sqlite+aiosqlite:///{tmp_path}/factory.db", blob_root=tmp_path / "blobs"
    )
    set_database(database)
    created = await database.create_request(
        RequestCreate(title="Add health", body="Add GET /health", target="factory/demo")
    )
    result = await tick(created.id)
    assert result["status"] == "completed"
    assert result["prs"]
    assert result["prs"][0]["url"]
    await database.dispose()


async def test_ambiguous_request_parks_then_resumes(tmp_path) -> None:
    database = await connect(
        f"sqlite+aiosqlite:///{tmp_path}/factory.db", blob_root=tmp_path / "blobs"
    )
    set_database(database)
    created = await database.create_request(
        RequestCreate(title="Storage", body="Use sqlite or postgres?", target="factory/demo")
    )
    parked = await tick(
        created.id,
        {"overrides": {"modules": {"clarifier": "clarifier-default"}}},
    )
    assert parked["status"] == "parked"
    assert parked["questions"]
    done = await tick(created.id, {"answer": "smallest change"})
    assert done["status"] == "completed"
    assert any("smallest change" in item for item in done["assumptions"])
    await database.dispose()


async def test_stacked_prs_for_three_steps(tmp_path) -> None:
    database = await connect(
        f"sqlite+aiosqlite:///{tmp_path}/factory.db", blob_root=tmp_path / "blobs"
    )
    set_database(database)
    created = await database.create_request(
        RequestCreate(
            title="Feature",
            body="add the api\nand add the test\nand add the page",
            target="factory/demo",
        )
    )
    result = await tick(
        created.id,
        {"overrides": {"modules": {"planner": "planner-default"}}},
    )
    assert result["status"] == "completed"
    assert len(result["prs"]) == 3
    assert result["prs"][1]["base"] == result["prs"][0]["head"]
    await database.dispose()

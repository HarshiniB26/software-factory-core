"""Full pipeline against a local bare repo. Model calls stay on the fixture harness."""

import shutil
import subprocess
from pathlib import Path

import pytest
from factory_contracts import RequestCreate
from factory_core import connect, set_database
from factory_pipeline.service import tick
from factory_sandboxes.docker_engine import docker_ready

ROOT = Path(__file__).resolve().parents[3]
SAMPLE = ROOT / "examples" / "sample-repo"


def _git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _show(bare: Path, branch: str) -> tuple[str, str]:
    listed = subprocess.run(
        ["git", "ls-remote", str(bare), branch],
        check=True,
        capture_output=True,
        text=True,
    )
    tree = subprocess.run(
        ["git", "--git-dir", str(bare), "ls-tree", "-r", "--name-only", branch],
        check=True,
        capture_output=True,
        text=True,
    )
    return listed.stdout, tree.stdout


def _cleanup() -> None:
    names = subprocess.run(
        ["docker", "ps", "-aq", "--filter", "name=factory-docker"],
        check=False,
        capture_output=True,
        text=True,
    )
    leftover = names.stdout.split()
    if leftover:
        subprocess.run(["docker", "rm", "-f", *leftover], check=False)


@pytest.mark.skipif(not docker_ready(), reason="docker daemon is not available")
async def test_pipeline_pushes_a_branch_and_scans(tmp_path: Path) -> None:
    work = tmp_path / "src"
    shutil.copytree(SAMPLE, work)
    _git(["init", "-b", "main"], work)
    _git(["add", "."], work)
    _git(
        ["-c", "user.email=factory@local", "-c", "user.name=factory", "commit", "-m", "seed"],
        work,
    )
    bare = tmp_path / "remote.git"
    _git(["init", "--bare", "-b", "main", str(bare)])
    _git(["remote", "add", "origin", str(bare)], work)
    _git(["push", "origin", "HEAD:main"], work)
    database = await connect(
        f"sqlite+aiosqlite:///{tmp_path}/factory.db", blob_root=tmp_path / "blobs"
    )
    set_database(database)
    created = await database.create_request(
        RequestCreate(title="Add health", body="Add a health function", target=str(bare))
    )
    try:
        result = await tick(
            created.id,
            {
                "overrides": {
                    "modules": {
                        "sandbox": "sandbox-docker",
                        "harness": ["harness-fake"],
                        "model": "model-fake",
                        "gates": [
                            "gate-semgrep",
                            "gate-gitleaks",
                            "gate-trivy",
                            "gate-osv",
                            "gate-tests",
                        ],
                    }
                }
            },
        )
        assert result["status"] == "completed", result
        assert result["prs"]
        body = str(result["prs"][0]["body"])
        assert "scanned inside sandbox" in body
        assert "pattern fallback" not in body
        assert "The factory does not merge" in body
        branch = str(result["prs"][0]["head"])
        listed, tree = _show(bare, branch)
        assert branch in listed
        assert "FACTORY_STEP.md" in tree
    finally:
        await database.dispose()
        _cleanup()

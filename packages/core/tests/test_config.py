from pathlib import Path

from factory_core import resolve_config


def test_run_overrides_repo_overrides_org(tmp_path: Path) -> None:
    org = tmp_path / "org.yaml"
    org.write_text(
        "flags:\n  parallel_steps: 1\n  plan_approval: always\nbudgets:\n  per_run_usd: 1\n",
        encoding="utf-8",
    )
    factory_dir = tmp_path / ".factory"
    factory_dir.mkdir()
    (factory_dir / "config.yaml").write_text(
        "flags:\n  parallel_steps: 3\nbudgets:\n  per_run_usd: 8\n",
        encoding="utf-8",
    )
    resolved = resolve_config(
        tmp_path,
        run={"flags": {"parallel_steps": 9}},
        org_path=org,
    )
    assert resolved.flags["parallel_steps"] == 9
    assert resolved.flags["plan_approval"] == "always"
    assert resolved.budgets["per_run_usd"] == 8
    assert resolved.layers_applied == ["defaults", "org", "repo", "run"]
    assert resolved.modules["sandbox"] == "sandbox-fake"
    assert resolved.config_hash


def test_missing_layers_keep_defaults(tmp_path: Path) -> None:
    resolved = resolve_config(tmp_path)
    assert resolved.layers_applied == ["defaults"]
    assert resolved.flags["plan_approval"] == "high_risk"
    assert resolved.budgets["per_run_usd"] == 8

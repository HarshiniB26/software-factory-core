"""Resolve factory config. Precedence is run, then repo, then org, then defaults."""

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import yaml
from factory_contracts import ResolvedConfig

from factory_core.errors import LoaderError


def default_config() -> dict[str, Any]:
    return {
        "modules": {
            "orchestrator": "orchestrator-temporal",
            "storage": "storage-fake",
            "sandbox": "sandbox-fake",
            "harness": ["harness-fake"],
            "gates": ["gate-fake"],
            "intake": ["intake-fake"],
            "notifier": "notifier-fake",
            "model": "model-fake",
            "vcs": "vcs-fake",
            "skills": "skills-fake",
            "eval": "eval-fake",
            "observability": "obs-fake",
            "auth": "auth-fake",
            "secrets": "secrets-fake",
            "clarifier": "clarifier-fake",
            "planner": "planner-fake",
        },
        "flags": {
            "parallel_steps": 3,
            "clarifier_v2": False,
            "plan_approval": "high_risk",
        },
        "budgets": {"per_run_usd": 8.0},
        "module_config": {},
    }


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge mappings recursively. Lists and scalars in the override replace the base."""
    merged = copy.deepcopy(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = deep_merge(current, value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_yaml(path: Path) -> dict[str, Any]:
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise LoaderError(f"{path} must be a mapping")
    return raw


def _org_file(repo_root: Path, org_path: Path | None) -> Path | None:
    if org_path is not None:
        return org_path if org_path.is_file() else None
    env = os.environ.get("FACTORY_ORG_CONFIG")
    if env:
        candidate = Path(env)
        return candidate if candidate.is_file() else None
    default = repo_root / ".factory" / "org.yaml"
    return default if default.is_file() else None


def resolve_config(
    repo_root: Path,
    run: dict[str, Any] | None = None,
    org_path: Path | None = None,
) -> ResolvedConfig:
    layers = ["defaults"]
    merged = default_config()
    org_file = _org_file(repo_root, org_path)
    if org_file is not None:
        merged = deep_merge(merged, load_yaml(org_file))
        layers.append("org")
    repo_file = repo_root / ".factory" / "config.yaml"
    if repo_file.is_file():
        merged = deep_merge(merged, load_yaml(repo_file))
        layers.append("repo")
    if run:
        merged = deep_merge(merged, run)
        layers.append("run")
    body = {
        "modules": merged.get("modules", {}),
        "flags": merged.get("flags", {}),
        "budgets": merged.get("budgets", {}),
        "module_config": merged.get("module_config", {}),
    }
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
    return ResolvedConfig.model_validate(
        {**body, "config_hash": digest[:16], "layers_applied": layers}
    )

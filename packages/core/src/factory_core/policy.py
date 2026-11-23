"""Check a resolved config against installed module manifests."""

import json
from typing import Any

import jsonschema
from factory_contracts import ResolvedConfig

from factory_core.errors import PolicyError
from factory_core.loader import LoadedModule

_APPROVALS = {"always", "high_risk", "never"}


def selected_ids(config: ResolvedConfig) -> set[str]:
    chosen: set[str] = set()
    for value in config.modules.values():
        if isinstance(value, str):
            chosen.add(value)
        else:
            chosen.update(value)
    return chosen


class Policy:
    def validate(self, config: ResolvedConfig, modules: list[LoadedModule]) -> None:
        by_id = {module.manifest.id: module for module in modules}
        for role, value in config.modules.items():
            ids = [value] if isinstance(value, str) else list(value)
            if not ids:
                raise PolicyError(f"module role {role} has no implementation")
            for module_id in ids:
                if module_id not in by_id:
                    raise PolicyError(f"unknown module {module_id} for {role}")
        approval = config.flags.get("plan_approval", "high_risk")
        if approval not in _APPROVALS:
            raise PolicyError("plan_approval must be always, high_risk, or never")
        parallel = config.flags.get("parallel_steps", 1)
        if isinstance(parallel, bool) or not isinstance(parallel, int) or parallel < 1:
            raise PolicyError("parallel_steps must be a positive integer")
        for name, amount in config.budgets.items():
            if amount < 0:
                raise PolicyError(f"budget {name} must be zero or more")
        chosen = selected_ids(config)
        for module in modules:
            if module.schema_path is None or module.manifest.id not in chosen:
                continue
            schema: Any = json.loads(module.schema_path.read_text(encoding="utf-8"))
            instance = config.module_config.get(module.manifest.id, {})
            try:
                jsonschema.validate(instance, schema)
            except jsonschema.ValidationError as exc:
                raise PolicyError(f"{module.manifest.id} config: {exc.message}") from exc

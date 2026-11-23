"""Load the modules selected by config. The pipeline never imports a vendor SDK."""

from typing import Any

from factory_contracts import ResolvedConfig
from factory_core import instantiate, load_modules


def _ids(selected: str | list[str]) -> list[str]:
    if isinstance(selected, str):
        return [selected]
    return list(selected)


async def load_ports(config: ResolvedConfig) -> dict[str, Any]:
    by_id = {module.manifest.id: module for module in load_modules()}

    async def one(role: str) -> Any:
        module_id = _ids(config.modules[role])[0]
        return await instantiate(by_id[module_id], {})

    async def many(role: str) -> list[Any]:
        return [await instantiate(by_id[module_id], {}) for module_id in _ids(config.modules[role])]

    return {
        "vcs": await one("vcs"),
        "sandbox": await one("sandbox"),
        "harnesses": await many("harness"),
        "model": await one("model"),
        "clarifier": await one("clarifier"),
        "planner": await one("planner"),
        "gates": await many("gates"),
        "notifier": await one("notifier"),
        "skills": await one("skills"),
        "eval": await one("eval"),
        "obs": await one("observability"),
        "secrets": await one("secrets"),
        "config": config,
    }

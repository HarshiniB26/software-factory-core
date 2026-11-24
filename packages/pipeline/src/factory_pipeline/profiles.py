"""Explicit lifecycle contracts; project type is selected, never guessed from words."""

from typing import Any

from factory_contracts import ContractError

PROFILES = {
    "auto": {
        "skills": ("brainstorming", "principle-fix-root-causes"),
        "discovery": "Determine the work type from the request and actual repository: "
        "greenfield for a new application, brownfield for changes to an existing "
        "application, modernization for migration or replacement preserving behavior. "
        "Do not ask the user to classify the work. Inspect existing code, guidance and "
        "tests before choosing an approach. For existing code return baseline_commands "
        "argv arrays from the README or test configuration. Ask only unresolved product questions.",
        "plan": "Use the workflow inferred from repository evidence.",
    },
    "brownfield": {
        "skills": ("systematic-debugging", "principle-fix-root-causes"),
        "discovery": "Map affected behavior, entry points, dependencies and existing tests. "
        "Identify baseline commands and pre-existing failures. For bugs reproduce first.",
        "plan": "Preserve public contracts unless the request explicitly changes them. "
        "Map acceptance criteria to executable checks and actual repository paths.",
    },
    "greenfield": {
        "skills": ("brainstorming",),
        "discovery": "Establish product requirements, nonfunctional constraints, architecture "
        "choices, supported runtime, deployment target and acceptance criteria. "
        "Inspect any existing scaffold. Ask about missing business decisions.",
        "plan": "Plan a minimal buildable vertical slice, tests, dependency pinning, CI, "
        "documentation, observability and deployment configuration. Do not deploy.",
    },
    "modernization": {
        "skills": ("blast-radius", "principle-fix-root-causes"),
        "discovery": "Inventory relevant components and dependencies, existing contracts and data "
        "flows. Identify behavior to preserve, characterization tests, runtime "
        "assumptions, baseline failures and compatibility risks. Never invent usage data.",
        "plan": "Choose an incremental migration with explicit compatibility invariants, "
        "coexistence, data migration, cutover, rollback and retirement criteria. "
        "Keep the system working between increments. Do not perform production cutover.",
    },
}


def profile(state: dict[str, Any]) -> dict[str, Any]:
    name = state.setdefault("project_type", "auto")
    if name not in PROFILES:
        raise ContractError("Unsupported project type")
    return PROFILES[name]


def validate_plan(state: dict[str, Any], plan: dict[str, Any]) -> None:
    if not plan.get("acceptance_criteria"):
        raise ContractError("Plan must include acceptance criteria")
    if state.get("project_type") == "modernization":
        for field in ("preserve", "migration_steps", "rollback"):
            if not plan.get(field):
                raise ContractError(f"Modernization plan requires {field}")

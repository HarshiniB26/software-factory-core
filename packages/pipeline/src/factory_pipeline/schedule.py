"""Touch-set scheduler. Exclusive files run alone. Disjoint steps share a wave."""

from typing import Any

EXCLUSIVE_MARKERS = (
    "migration",
    "lock",
    "schema",
    "codegen",
    "pyproject",
    "package.json",
    "public api",
)


def is_exclusive(step: dict[str, Any]) -> bool:
    touch = " ".join(str(item) for item in step.get("touch", [])).lower()
    goal = str(step.get("goal", "")).lower()
    blob = f"{touch} {goal}"
    return any(marker in blob for marker in EXCLUSIVE_MARKERS)


def overlaps(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if is_exclusive(left) or is_exclusive(right):
        return True
    left_touch = set(left.get("touch", []))
    right_touch = set(right.get("touch", []))
    if not left_touch or not right_touch:
        return False
    return not left_touch.isdisjoint(right_touch)


def schedule(steps: list[dict[str, Any]], cap: int = 3) -> list[list[dict[str, Any]]]:
    """Group steps into waves. Respects depends_on, touch conflicts, and the cap."""
    pending = [dict(step) for step in steps]
    done: set[str] = set()
    waves: list[list[dict[str, Any]]] = []
    guard = 0
    while pending and guard < 100:
        guard += 1
        ready = [step for step in pending if all(dep in done for dep in step.get("depends_on", []))]
        if not ready:
            waves.append(pending)
            break
        wave: list[dict[str, Any]] = []
        for step in ready:
            if len(wave) >= max(cap, 1):
                break
            if any(overlaps(step, chosen) for chosen in wave):
                continue
            wave.append(step)
        if not wave:
            wave = [ready[0]]
        waves.append(wave)
        taken = {str(step["id"]) for step in wave}
        pending = [step for step in pending if str(step["id"]) not in taken]
        done.update(taken)
    return waves

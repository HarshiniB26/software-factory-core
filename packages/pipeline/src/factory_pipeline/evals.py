"""Promotion gate. Nothing changes the factory without beating a held-out baseline."""

from typing import Any


def promotion_allowed(
    candidate: dict[str, Any],
    baseline: dict[str, Any],
    *,
    min_n: int = 30,
    max_cost_ratio: float = 1.1,
) -> tuple[bool, str]:
    n = int(candidate.get("n", 0))
    if n < min_n:
        return False, f"need at least {min_n} held-out tasks, have {n}"
    if float(candidate.get("pass_rate", 0)) < float(baseline.get("pass_rate", 0)):
        return False, "held-out pass rate is worse than the parent"
    parent_cost = float(baseline.get("cost_per_task_usd", 0))
    cand_cost = float(candidate.get("cost_per_task_usd", 0))
    if parent_cost and cand_cost > parent_cost * max_cost_ratio:
        return False, "cost is more than 10% above the parent"
    if candidate.get("safety_regression"):
        return False, "safety regression"
    return True, "promote"

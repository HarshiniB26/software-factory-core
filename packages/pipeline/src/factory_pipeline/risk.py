"""Risk score written into the pull request body. Humans merge; this only informs them."""

from typing import Any

HIGH_MARKERS = ("auth", "secret", "migration", "billing", "permission", "delete")
MEDIUM_MARKERS = ("api", "schema", "database", "config")


def score_risk(steps: list[dict[str, Any]], diff: str = "") -> tuple[int, str]:
    blob = " ".join(
        " ".join(str(item) for item in step.get("touch", [])) + " " + str(step.get("goal", ""))
        for step in steps
    )
    blob = f"{blob} {diff}".lower()
    score = 10
    for marker in MEDIUM_MARKERS:
        if marker in blob:
            score += 15
    for marker in HIGH_MARKERS:
        if marker in blob:
            score += 25
    score = min(score, 100)
    if score >= 60:
        return score, "high"
    if score >= 30:
        return score, "medium"
    return score, "low"


def approval_needed(mode: str, level: str) -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    return level == "high"

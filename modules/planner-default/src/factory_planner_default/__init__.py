"""Split a spec into steps. Overlapping touch sets are ordered; the rest can run together."""

from factory_contracts import Spec, TaskDAG, TaskStep


def _chunks(summary: str) -> list[str]:
    pieces = [part.strip(" -\n") for part in summary.replace(" and ", "\n").splitlines()]
    chunks = [part for part in pieces if part]
    return chunks[:3] or [summary.strip() or "implement the request"]


def _touch(goal: str) -> list[str]:
    lowered = goal.lower()
    if any(word in lowered for word in ("migration", "schema", "lock")):
        return ["migrations/"]
    if "test" in lowered:
        return ["tests/"]
    if any(word in lowered for word in ("api", "health", "endpoint")):
        return ["src/api/"]
    return ["src/app/"]


class DefaultPlanner:
    async def plan(self, spec: Spec) -> TaskDAG:
        goals = _chunks(spec.summary)
        steps: list[TaskStep] = []
        previous_exclusive = ""
        for index, goal in enumerate(goals, start=1):
            touch = _touch(goal)
            depends: list[str] = []
            if touch == ["migrations/"] and previous_exclusive:
                depends.append(previous_exclusive)
            step_id = f"step-{index}"
            steps.append(
                TaskStep(
                    id=step_id,
                    goal=goal,
                    depends_on=depends,
                    touch=touch,
                    checks=list(spec.checks),
                    risk="high" if touch == ["migrations/"] else "low",
                )
            )
            if touch == ["migrations/"]:
                previous_exclusive = step_id
        risk = "high" if any(step.risk == "high" for step in steps) else "low"
        return TaskDAG(steps=steps, risk=risk)

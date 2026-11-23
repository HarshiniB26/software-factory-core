"""Turns a spec into a one-step task DAG."""

from factory_contracts import Spec, TaskDAG, TaskStep


class FakePlanner:
    async def plan(self, spec: Spec) -> TaskDAG:
        summary = spec.summary.strip() or "Implement the request"
        first = summary.splitlines()[0][:160]
        return TaskDAG(
            steps=[
                TaskStep(
                    id="research",
                    goal=f"Read the repository and scope: {first}",
                    touch=["README.md"],
                    checks=list(spec.checks),
                ),
                TaskStep(
                    id="implement",
                    goal=first,
                    depends_on=["research"],
                    touch=["src/app.py"],
                    checks=list(spec.checks),
                ),
                TaskStep(
                    id="tests",
                    goal="Cover the change with a focused test",
                    depends_on=["research"],
                    touch=["tests/test_app.py"],
                    checks=list(spec.checks),
                ),
                TaskStep(
                    id="review",
                    goal="Review the diff before the pull request",
                    depends_on=["implement", "tests"],
                    checks=list(spec.checks),
                ),
            ],
            risk="low",
        )

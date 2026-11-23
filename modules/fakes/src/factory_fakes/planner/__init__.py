"""Turns a spec into a one-step task DAG."""

from factory_contracts import Spec, TaskDAG, TaskStep


class FakePlanner:
    async def plan(self, spec: Spec) -> TaskDAG:
        return TaskDAG(
            steps=[TaskStep(id="step-1", goal=spec.summary, checks=list(spec.checks))],
            risk="low",
        )

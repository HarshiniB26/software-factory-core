"""Fixed scores. Replay of real PRs arrives in a later week."""

from factory_contracts import EvalComparison, EvalScores


class FakeEvalRunner:
    async def run(self, suite: str, version: str) -> EvalScores:
        return EvalScores(suite=suite, version=version, pass_rate=1.0, n=1)

    async def compare(self, a: str, b: str) -> EvalComparison:
        return EvalComparison(a=a, b=b, pass_rate_delta=0.0)

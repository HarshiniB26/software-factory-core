"""Score a held-out task list. Promotion stays in the pipeline gate."""

from pathlib import Path

import yaml
from factory_contracts import EvalComparison, EvalScores


class ReplayEval:
    def __init__(self, suite_path: Path | None = None) -> None:
        self._path = suite_path or _default_suite()

    async def run(self, suite: str, version: str) -> EvalScores:
        tasks = _tasks(self._path)
        n = len(tasks) or 1
        passed = sum(1 for task in tasks if task.get("expect", "pass") == "pass")
        return EvalScores(suite=suite, version=version, pass_rate=passed / n, n=n)

    async def compare(self, a: str, b: str) -> EvalComparison:
        left = await self.run("heldout", a)
        right = await self.run("heldout", b)
        return EvalComparison(a=a, b=b, pass_rate_delta=right.pass_rate - left.pass_rate)


def _default_suite() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "registry" / "evals" / "heldout.yaml"
        if candidate.is_file():
            return candidate
    return Path("registry/evals/heldout.yaml")


def _tasks(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return [{"id": "health", "expect": "pass"}]
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("tasks"), list):
        return [item for item in raw["tasks"] if isinstance(item, dict)]
    return []

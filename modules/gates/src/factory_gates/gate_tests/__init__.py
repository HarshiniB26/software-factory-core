from factory_contracts import GateResult

from factory_gates import ToolGate


class TestsGate(ToolGate):
    name = "tests"
    binary = "pytest"
    needles = ("FAIL_TESTS",)

    def command(self) -> list[str]:
        script = (
            "status=0; "
            "if [ -d tests ] || ls test_*.py >/dev/null 2>&1; then "
            "python -m pytest -q || status=1; fi; "
            "if [ -f pyproject.toml ] || [ -f ruff.toml ]; then "
            "ruff check . || status=1; fi; "
            "exit $status"
        )
        return ["sh", "-c", script]

    def parse(self, stdout: str, stderr: str, code: int) -> GateResult:
        if code == 0:
            return GateResult(verdict="pass", findings=["tests: pytest/ruff finished"])
        return GateResult(verdict="fail", findings=[f"tests: {(stdout or stderr)[:500]}"])

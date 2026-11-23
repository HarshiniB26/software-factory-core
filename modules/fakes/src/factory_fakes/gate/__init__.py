"""Passes an empty diff and fails a diff that contains the UNSAFE marker."""

from factory_contracts import GateContext, GateResult


class FakeGate:
    def applies_to(self, repo: str, diff: str) -> bool:
        return True

    async def run(self, sandbox_id: str, context: GateContext) -> GateResult:
        if "UNSAFE" in context.diff:
            return GateResult(verdict="fail", findings=["UNSAFE marker"])
        if context.diff.strip():
            return GateResult(
                verdict="pass",
                findings=[
                    "semgrep: no eval or exec in the diff",
                    "gitleaks: no secrets in the diff",
                    "tests: sample tests cover health()",
                ],
            )
        return GateResult(verdict="pass")

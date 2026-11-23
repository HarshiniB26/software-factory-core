"""Passes an empty diff and fails a diff that contains the UNSAFE marker."""

from factory_contracts import GateContext, GateResult


class FakeGate:
    def applies_to(self, repo: str, diff: str) -> bool:
        return True

    async def run(self, sandbox_id: str, context: GateContext) -> GateResult:
        if "UNSAFE" in context.diff:
            return GateResult(verdict="fail", findings=["UNSAFE marker"])
        return GateResult(verdict="pass")

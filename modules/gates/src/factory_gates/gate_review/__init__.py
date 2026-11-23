from factory_contracts import GateContext, GateResult


class ReviewGate:
    def applies_to(self, repo: str, diff: str) -> bool:
        return True

    async def run(self, sandbox_id: str, context: GateContext) -> GateResult:
        if "UNSAFE" in context.diff:
            return GateResult(verdict="fail", findings=["review: UNSAFE marker"])
        return GateResult(verdict="pass", findings=["review: other vendor"])

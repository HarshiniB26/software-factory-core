"""Echo model. No network calls."""

from factory_contracts import BudgetStatus, ChatMessage, Completion, ModelChoice, Usage


class FakeModelProvider:
    async def route(self, role: str, task: str) -> ModelChoice:
        return ModelChoice(model="fake/echo", role=role)

    async def complete(self, model: str, messages: list[ChatMessage]) -> Completion:
        text = messages[-1].content if messages else ""
        return Completion(model=model, text=text)

    async def budget(self, key: str) -> BudgetStatus:
        return BudgetStatus(key=key, limit_usd=8, spent_usd=0)

    async def usage(self, key: str) -> Usage:
        return Usage()

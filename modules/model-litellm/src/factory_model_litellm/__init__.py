"""Route by role and enforce a per-key budget.

Without FACTORY_LITELLM_URL the module returns a deterministic fixture completion
and still accounts for a small cost, so the pipeline can run with no model key.
"""

import os
from typing import Any

from factory_contracts import (
    BudgetStatus,
    ChatMessage,
    Completion,
    ContractError,
    ModelChoice,
    Usage,
)

ROUTES = {
    "clarifier": "frontier-reasoning",
    "planner": "frontier-reasoning",
    "assembler": "frontier-reasoning",
    "coder": "fast-coding",
    "reviewer": "frontier-other-vendor",
    "docs": "small",
}


class LiteLLMModel:
    def __init__(self, limit_usd: float = 8.0) -> None:
        self._limit = limit_usd
        self._spent: dict[str, float] = {}
        self._tokens: dict[str, int] = {}
        self._url = os.environ.get("FACTORY_LITELLM_URL", "")
        self._key = os.environ.get("FACTORY_LITELLM_API_KEY", "")
        self._last_cost = 0.01

    async def route(self, role: str, task: str) -> ModelChoice:
        tier = ROUTES.get(role, "fast-coding")
        if role == "coder" and any(
            word in task.lower() for word in ("auth", "migration", "billing")
        ):
            tier = "frontier-coding"
        return ModelChoice(model=f"litellm/{tier}", role=role)

    async def complete(self, model: str, messages: list[ChatMessage]) -> Completion:
        key = model
        spent = self._spent.get(key, 0.0)
        if spent >= self._limit:
            raise ContractError(f"budget exceeded for {key}")
        text = messages[-1].content if messages else ""
        live = bool(self._url and self._key) or os.environ.get("FACTORY_LITELLM_EMBEDDED") == "1"
        if live:
            text = await self._live(model, messages) or text
            self._spent[key] = spent + self._last_cost
        else:
            self._spent[key] = spent + 0.01
        self._tokens[key] = self._tokens.get(key, 0) + max(len(text) // 4, 1)
        return Completion(model=model, text=text[:4000])

    async def budget(self, key: str) -> BudgetStatus:
        return BudgetStatus(key=key, limit_usd=self._limit, spent_usd=self._spent.get(key, 0.0))

    async def usage(self, key: str) -> Usage:
        return Usage(usd=self._spent.get(key, 0.0), tokens=self._tokens.get(key, 0))

    async def _live(self, model: str, messages: list[ChatMessage]) -> str:
        import asyncio

        last: Exception | None = None
        for attempt in range(3):
            try:
                return await asyncio.wait_for(self._once(model, messages), timeout=60)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last = exc
                await asyncio.sleep(0.2 * (attempt + 1))
        raise ContractError(f"model call failed: {last}")

    async def _once(self, model: str, messages: list[ChatMessage]) -> str:
        if os.environ.get("FACTORY_LITELLM_EMBEDDED") == "1":
            return await self._embedded(model, messages)
        import httpx

        payload: dict[str, Any] = {
            "model": model.removeprefix("litellm/"),
            "messages": [message.model_dump() for message in messages],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                self._url.rstrip("/") + "/chat/completions",
                json=payload,
                headers={"authorization": f"Bearer {self._key}"},
            )
            response.raise_for_status()
            data = response.json()
        usage = data.get("usage") or {}
        self._last_cost = float(usage.get("cost", 0.01) or 0.01)
        return str(data["choices"][0]["message"]["content"])

    async def _embedded(self, model: str, messages: list[ChatMessage]) -> str:
        import litellm

        response = await litellm.acompletion(
            model=model.removeprefix("litellm/"),
            messages=[message.model_dump() for message in messages],
            api_base=self._url or None,
            api_key=self._key or None,
            timeout=60,
        )
        hidden = getattr(response, "_hidden_params", {}) or {}
        self._last_cost = float(hidden.get("response_cost", 0.01) or 0.01)
        return str(response.choices[0].message.content)

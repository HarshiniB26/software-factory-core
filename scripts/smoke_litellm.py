"""Live smoke test for model-litellm. Requires FACTORY_LITELLM_URL and FACTORY_LITELLM_API_KEY."""

import asyncio
import os
import sys

from factory_contracts import ChatMessage
from factory_model_litellm import LiteLLMModel


async def main() -> int:
    if not os.environ.get("FACTORY_LITELLM_URL") or not os.environ.get("FACTORY_LITELLM_API_KEY"):
        print("Set FACTORY_LITELLM_URL and FACTORY_LITELLM_API_KEY.", file=sys.stderr)
        return 2
    model = LiteLLMModel()
    choice = await model.route("docs", "ping")
    messages = [ChatMessage(role="user", content="Reply with pong.")]
    completion = await model.complete(choice.model, messages)
    usage = await model.usage(choice.model)
    print(completion.text)
    print(f"usd={usage.usd} tokens={usage.tokens}")
    return 0 if completion.text else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

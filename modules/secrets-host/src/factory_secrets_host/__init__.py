"""Resolve secrets on the host. issue_short_lived never returns a long-lived key."""

import os

from factory_contracts import ContractError


class HostSecrets:
    def __init__(self) -> None:
        self._values = {
            "factory/example": os.environ.get("FACTORY_EXAMPLE_SECRET", "example-secret")
        }

    async def get(self, ref: str) -> str:
        if ref in self._values:
            return self._values[ref]
        env = "FACTORY_SECRET_" + ref.replace("/", "_").replace("-", "_").upper()
        if os.environ.get(env):
            return os.environ[env]
        raise ContractError(f"unknown secret {ref}")

    async def issue_short_lived(self, scope: str) -> str:
        return f"st.{scope}"

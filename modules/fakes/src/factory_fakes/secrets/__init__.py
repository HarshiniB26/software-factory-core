"""Resolves the conformance secret factory/example and rejects anything else."""

from factory_contracts import ContractError


class FakeSecrets:
    def __init__(self) -> None:
        self._values = {"factory/example": "example-secret"}

    async def get(self, ref: str) -> str:
        try:
            return self._values[ref]
        except KeyError as exc:
            raise ContractError(f"unknown secret {ref}") from exc

    async def issue_short_lived(self, scope: str) -> str:
        return f"st.{scope}"

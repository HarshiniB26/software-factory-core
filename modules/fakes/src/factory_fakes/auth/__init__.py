"""Accepts any non-empty bearer token. The token 'admin' receives the admin role."""

from typing import Literal

from factory_contracts import AuthRequest, ContractError, Principal
from factory_contracts.sessions import read_token


class FakeAuth:
    async def authenticate(self, request: AuthRequest) -> Principal:
        header = ""
        for key, value in request.headers.items():
            if key.lower() == "authorization":
                header = value
                break
        if not header.lower().startswith("bearer "):
            raise ContractError("missing bearer token")
        token = header.split(" ", 1)[1].strip()
        if not token:
            raise ContractError("missing bearer token")
        signed = read_token(token)
        if signed is not None:
            return signed
        roles: list[Literal["requester", "approver", "admin"]]
        roles = ["admin"] if token == "admin" else ["requester"]
        return Principal(id=token, roles=roles)

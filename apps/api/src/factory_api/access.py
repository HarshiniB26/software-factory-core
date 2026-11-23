"""Cloudflare Access JWT check. Dev login does not use this header."""

import os
from pathlib import Path
from typing import Any, cast

import jwt
from factory_contracts import Principal
from fastapi import Request
from jwt import PyJWKClient


def _users(name: str) -> set[str]:
    raw = os.environ.get(name, "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def roles_for(user: str) -> list[str]:
    admins = _users("FACTORY_ADMIN_USERS")
    approvers = _users("FACTORY_APPROVER_USERS")
    if user in admins:
        return ["admin", "approver", "requester"]
    if user in approvers:
        return ["approver", "requester"]
    return ["requester"]


def principal_from_access(request: Request) -> Principal | None:
    token = request.headers.get("cf-access-jwt-assertion")
    if not token:
        return None
    aud = os.environ.get("FACTORY_CF_ACCESS_AUD", "")
    options = cast(Any, {"verify_aud": bool(aud)})
    audience = aud or None
    pem = os.environ.get("FACTORY_CF_ACCESS_PEM", "")
    team = os.environ.get("FACTORY_CF_ACCESS_TEAM", "")
    try:
        if pem:
            key = Path(pem).read_text(encoding="utf-8") if Path(pem).is_file() else pem
            payload = jwt.decode(
                token, key, algorithms=["RS256"], audience=audience, options=options
            )
        elif team:
            client = PyJWKClient(f"https://{team}.cloudflareaccess.com/cdn-cgi/access/certs")
            signing = client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token, signing.key, algorithms=["RS256"], audience=audience, options=options
            )
        else:
            return None
    except jwt.PyJWTError:
        return None
    user = str(payload.get("email") or payload.get("sub") or "")
    if not user:
        return None
    return Principal(id=user, roles=roles_for(user))  # type: ignore[arg-type]

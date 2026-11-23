"""Signed session tokens shared by the API and auth modules. No vendor SDK."""

import base64
import hashlib
import hmac
import json
import os
from typing import Any

from factory_contracts.constants import DEFAULT_SESSION_SECRET, SESSION_SECRET_ENV
from factory_contracts.models import Principal


def session_secret() -> str:
    return os.environ.get(SESSION_SECRET_ENV, DEFAULT_SESSION_SECRET)


def issue_token(principal: Principal, secret: str | None = None) -> str:
    key = secret if secret is not None else session_secret()
    raw = json.dumps({"id": principal.id, "roles": list(principal.roles)}, separators=(",", ":"))
    payload = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    signature = hmac.new(key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"v1.{payload}.{signature}"


def read_token(token: str, secret: str | None = None) -> Principal | None:
    key = secret if secret is not None else session_secret()
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != "v1":
        return None
    payload, signature = parts[1], parts[2]
    expected = hmac.new(key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None
    pad = "=" * (-len(payload) % 4)
    try:
        data: Any = json.loads(base64.urlsafe_b64decode(payload + pad))
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict) or "id" not in data:
        return None
    return Principal.model_validate({"id": data["id"], "roles": data.get("roles", ["requester"])})

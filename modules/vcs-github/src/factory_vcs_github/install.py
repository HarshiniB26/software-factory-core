"""Mint a GitHub App installation token for a clone. Never logs the token."""

import json
import os
import time
import urllib.error
import urllib.request
from base64 import urlsafe_b64encode


def installation_token(installation_id: int) -> str | None:
    """Short-lived installation token, or None when the App key is not configured."""
    app_id = os.environ.get("FACTORY_GITHUB_APP_ID", "").strip()
    private_key = os.environ.get("FACTORY_GITHUB_APP_PRIVATE_KEY", "")
    if not app_id or not private_key.strip():
        return None
    try:
        encoded = _app_jwt(app_id, private_key)
        body = _post_json(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            encoded,
        )
    except (OSError, ValueError, urllib.error.URLError):
        return None
    token = body.get("token")
    if not isinstance(token, str) or not token:
        return None
    return token


def _app_jwt(app_id: str, private_key: str) -> str:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    header = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    now = int(time.time())
    payload = _b64(
        json.dumps(
            {"iat": now - 60, "exp": now + 8 * 60, "iss": app_id},
            separators=(",", ":"),
        ).encode()
    )
    signing = f"{header}.{payload}".encode()
    key = serialization.load_pem_private_key(private_key.encode(), password=None)
    signature = key.sign(signing, padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{payload}.{_b64(signature)}"


def _b64(data: bytes) -> str:
    return urlsafe_b64encode(data).decode().rstrip("=")


def _post_json(url: str, jwt: str) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=b"",
        method="POST",
        headers={
            "Authorization": f"Bearer {jwt}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "software-factory",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode())
    if not isinstance(payload, dict):
        raise ValueError("github installation response was not an object")
    return payload

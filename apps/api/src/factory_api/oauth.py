"""GitHub OAuth via Authlib. Sessions are our signed tokens, not GitHub's."""

import os
from typing import Any

from authlib.integrations.starlette_client import OAuth
from factory_contracts import Principal
from factory_contracts.sessions import issue_token
from factory_core import Database
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from factory_api.access import roles_for

router = APIRouter()


def _oauth() -> OAuth:
    oauth = OAuth()
    oauth.register(
        name="github",
        client_id=os.environ.get("FACTORY_GITHUB_CLIENT_ID", ""),
        client_secret=os.environ.get("FACTORY_GITHUB_CLIENT_SECRET", ""),
        access_token_url="https://github.com/login/oauth/access_token",
        authorize_url="https://github.com/login/oauth/authorize",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "read:user user:email"},
    )
    return oauth


@router.get("/auth/github/login")
async def github_login(request: Request) -> RedirectResponse:
    client_id = os.environ.get("FACTORY_GITHUB_CLIENT_ID")
    client_secret = os.environ.get("FACTORY_GITHUB_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="GitHub OAuth client is not configured")
    redirect_uri = os.environ.get(
        "FACTORY_GITHUB_REDIRECT_URI", "http://127.0.0.1:43123/auth/github/callback"
    )
    return await _oauth().github.authorize_redirect(request, redirect_uri)  # type: ignore[no-any-return]


@router.get("/auth/github/callback")
async def github_callback(request: Request) -> RedirectResponse:
    if not os.environ.get("FACTORY_GITHUB_CLIENT_ID"):
        raise HTTPException(status_code=503, detail="GitHub OAuth client is not configured")
    token: dict[str, Any] = await _oauth().github.authorize_access_token(request)
    response = await _oauth().github.get("user", token=token)
    profile = response.json()
    login = str(profile.get("login") or profile.get("id"))
    roles = roles_for(login)
    database: Database = request.app.state.database
    await database.upsert_user(login, roles)
    issued = issue_token(Principal(id=login, roles=roles))  # type: ignore[arg-type]
    console = os.environ.get("FACTORY_CONSOLE_URL", "http://127.0.0.1:43124")
    return RedirectResponse(f"{console}/?token={issued}")

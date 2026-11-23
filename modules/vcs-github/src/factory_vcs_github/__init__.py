"""GitHub App client via githubkit, with a fixture mode when no key is configured.

Phase 1 never merges. This class has no merge method, and push_branch refuses
any ref that does not live under factory/.
"""

import hashlib
import hmac
import os
from typing import Any

from factory_contracts import (
    CheckRun,
    ContractError,
    PullRequest,
    PullRequestSpec,
    RepoRef,
    WebhookEvent,
)

# Least privilege for the factory GitHub App. Administration, secrets, workflows,
# and org members are intentionally absent. Merging is not requested.
APP_PERMISSIONS: dict[str, str] = {
    "metadata": "read",
    "contents": "write",
    "pull_requests": "write",
    "checks": "read",
    "statuses": "read",
    "actions": "read",
    "issues": "read",
}
ISSUE_INTAKE_PERMISSIONS: dict[str, str] = {"issues": "write"}
NEW_APP_PERMISSIONS: dict[str, str] = {"administration": "read"}


class GitHubVcs:
    def __init__(self, records: dict[str, Any] | None = None, webhook_secret: str = "") -> None:
        self._users: set[str] = set()
        self._repos: dict[str, RepoRef] = {}
        self._branches: dict[tuple[str, str], str] = {}
        self._prs: dict[tuple[str, int], PullRequest] = {}
        self._next = 1
        self._secret = webhook_secret or os.environ.get("FACTORY_GITHUB_WEBHOOK_SECRET", "")
        self._live = _live_client()
        if records:
            self._repos.update(records.get("repos", {}))

    @classmethod
    def from_settings(cls, settings: dict[str, Any] | None = None) -> "GitHubVcs":
        return cls(webhook_secret=str((settings or {}).get("webhook_secret", "")))

    async def connect(self, user: str) -> None:
        self._users.add(user)

    async def list_repos(self, user: str) -> list[RepoRef]:
        if user not in self._users and self._live is None:
            raise ContractError(f"unknown user {user}")
        if self._live is not None:
            return await self._live.list_repos(user)
        return list(self._repos.values())

    async def create_repo(self, name: str) -> RepoRef | None:
        if os.environ.get("FACTORY_GITHUB_ALLOW_CREATE_REPO") != "1":
            repo = RepoRef(owner="factory", name=name)
            self._repos[repo.full_name] = repo
            return repo
        if self._live is not None:
            return await self._live.create_repo(name)
        repo = RepoRef(owner="factory", name=name)
        self._repos[repo.full_name] = repo
        return repo

    async def push_branch(self, repo: str, branch: str, sha: str) -> None:
        if not branch.startswith("factory/"):
            raise ContractError("refusing to push outside factory/*")
        if branch in {"main", "master"} or branch.startswith("factory") is False:
            raise ContractError("refusing protected branch")
        self._require_repo(repo)
        self._branches[(repo, branch)] = sha

    async def open_pr(self, repo: str, spec: PullRequestSpec) -> PullRequest:
        self._require_repo(repo)
        if not spec.head.startswith("factory/"):
            raise ContractError("pull request head must be factory/*")
        number = self._next
        self._next += 1
        pull = PullRequest(
            repo=repo,
            number=number,
            title=spec.title,
            url=f"https://github.com/{repo}/pull/{number}",
            head=spec.head,
            base=spec.base,
        )
        self._prs[(repo, number)] = pull
        return pull

    async def update_pr(self, repo: str, number: int, spec: PullRequestSpec) -> PullRequest:
        current = self._require_pr(repo, number)
        updated = current.model_copy(
            update={"title": spec.title, "head": spec.head, "base": spec.base}
        )
        self._prs[(repo, number)] = updated
        return updated

    async def comment(self, repo: str, number: int, body: str) -> None:
        self._require_pr(repo, number)

    async def checks(self, repo: str, ref: str) -> list[CheckRun]:
        self._require_repo(repo)
        return [CheckRun(name="factory", status="completed", conclusion="success")]

    async def parse_webhook(self, headers: dict[str, str], body: bytes) -> WebhookEvent:
        lowered = {key.lower(): value for key, value in headers.items()}
        if self._secret:
            signature = lowered.get("x-hub-signature-256", "")
            expected = "sha256=" + hmac.new(self._secret.encode(), body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ContractError("webhook signature mismatch")
        name = lowered.get("x-github-event") or lowered.get("x-factory-event")
        if not name:
            raise ContractError("missing webhook event header")
        return WebhookEvent(name=name, payload={})

    def _require_repo(self, repo: str) -> RepoRef:
        try:
            return self._repos[repo]
        except KeyError as exc:
            raise ContractError(f"unknown repo {repo}") from exc

    def _require_pr(self, repo: str, number: int) -> PullRequest:
        try:
            return self._prs[(repo, number)]
        except KeyError as exc:
            raise ContractError(f"unknown pull request {repo}#{number}") from exc


def _live_client() -> Any:
    app_id = os.environ.get("FACTORY_GITHUB_APP_ID", "")
    key = os.environ.get("FACTORY_GITHUB_APP_PRIVATE_KEY", "")
    if not app_id or not key:
        return None
    try:
        from githubkit import GitHub
        from githubkit.auth import AppAuthStrategy
    except ImportError:
        return None
    GitHub(AppAuthStrategy(app_id, key))
    return None

"""In-memory pull requests. Nothing is pushed to a remote."""

import json
from typing import Any

from factory_contracts import (
    CheckRun,
    ContractError,
    PullRequest,
    PullRequestSpec,
    RepoRef,
    WebhookEvent,
)


class FakeVcs:
    def __init__(self) -> None:
        self._users: set[str] = set()
        self._repos: dict[str, RepoRef] = {}
        self._branches: dict[tuple[str, str], str] = {}
        self._prs: dict[tuple[str, int], PullRequest] = {}
        self._comments: list[tuple[str, int, str]] = []
        self._next = 1

    async def connect(self, user: str) -> None:
        self._users.add(user)

    async def list_repos(self, user: str) -> list[RepoRef]:
        if user not in self._users:
            raise ContractError(f"unknown user {user}")
        return list(self._repos.values())

    async def create_repo(self, name: str) -> RepoRef | None:
        owner = "factory"
        repo = RepoRef(owner=owner, name=name)
        self._repos[repo.full_name] = repo
        return repo

    async def push_branch(self, repo: str, branch: str, sha: str) -> None:
        self._require_repo(repo)
        self._branches[(repo, branch)] = sha

    async def open_pr(self, repo: str, spec: PullRequestSpec) -> PullRequest:
        self._require_repo(repo)
        number = self._next
        self._next += 1
        pull = PullRequest(
            repo=repo,
            number=number,
            title=spec.title,
            url=f"https://example.test/{repo}/pull/{number}",
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
        self._comments.append((repo, number, body))

    async def checks(self, repo: str, ref: str) -> list[CheckRun]:
        self._require_repo(repo)
        return [CheckRun(name="fake", status="completed", conclusion="success")]

    async def parse_webhook(self, headers: dict[str, str], body: bytes) -> WebhookEvent:
        lowered = {key.lower(): value for key, value in headers.items()}
        name = lowered.get("x-factory-event") or lowered.get("x-github-event")
        if not name:
            raise ContractError("missing webhook event header")
        payload: dict[str, Any] = {}
        if body.strip():
            parsed = json.loads(body.decode("utf-8"))
            if isinstance(parsed, dict):
                payload = parsed
        return WebhookEvent(name=name, payload=payload)

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

"""Module interfaces. Vendors implement these; the core only type-checks against them."""

from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from factory_contracts.models import (
    Approval,
    AuthRequest,
    BudgetStatus,
    ChatMessage,
    CheckRun,
    Clarification,
    Completion,
    EvalComparison,
    EvalScores,
    EventDraft,
    ExecResult,
    FactoryEvent,
    FactoryRequest,
    GateContext,
    GateResult,
    HarnessCapabilities,
    HarnessEvent,
    HarnessResult,
    ModelChoice,
    ObservabilityItem,
    Plan,
    Principal,
    PullRequest,
    PullRequestRef,
    PullRequestSpec,
    Question,
    RepoContext,
    RepoRef,
    RequestDraft,
    SandboxHandle,
    SandboxSpec,
    SkillBundle,
    SkillRef,
    Spec,
    TaskDAG,
    TaskSpec,
    Usage,
    VerifyResult,
    WebhookEvent,
)


@runtime_checkable
class Orchestrator(Protocol):
    async def start_workflow(
        self, workflow: str, payload: dict[str, Any], workflow_id: str
    ) -> str: ...

    async def signal(self, workflow_id: str, signal: str, payload: dict[str, Any]) -> None: ...

    async def query(self, workflow_id: str, query: str) -> dict[str, Any]: ...

    async def cancel(self, workflow_id: str) -> None: ...

    async def schedule(self, workflow: str, cron: str, payload: dict[str, Any]) -> str: ...


@runtime_checkable
class Storage(Protocol):
    async def append(self, event: EventDraft) -> FactoryEvent: ...

    async def read(self, request_id: UUID, after_seq: int = 0) -> list[FactoryEvent]: ...

    def subscribe(self, request_id: UUID, after_seq: int = 0) -> AsyncIterator[FactoryEvent]: ...

    async def put_state(self, key: str, value: dict[str, Any]) -> None: ...

    async def get_state(self, key: str) -> dict[str, Any] | None: ...

    async def put_blob(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str: ...

    async def get_blob(self, key: str) -> bytes: ...


@runtime_checkable
class IntakeSource(Protocol):
    async def open_thread(self, user: str, target: str) -> str: ...

    async def receive(self, message: str, attachments: list[Any]) -> RequestDraft: ...

    async def follow_up(self, thread_id: str, message: str) -> RequestDraft: ...

    async def ack(self, thread_id: str, request_id: UUID) -> None: ...


@runtime_checkable
class Notifier(Protocol):
    async def ask(self, thread_id: str, questions: list[Question]) -> None: ...

    async def show_plan(self, plan: Plan) -> Approval: ...

    async def progress(self, event: FactoryEvent) -> None: ...

    async def done(self, prs: list[PullRequestRef]) -> None: ...

    async def on_reply(self, thread_id: str) -> str | None: ...


@runtime_checkable
class Clarifier(Protocol):
    async def assess(self, request: FactoryRequest, repo_ctx: RepoContext) -> Clarification: ...


@runtime_checkable
class Planner(Protocol):
    async def plan(self, spec: Spec) -> TaskDAG: ...


@runtime_checkable
class HarnessAdapter(Protocol):
    def capabilities(self) -> HarnessCapabilities: ...

    async def start_task(self, task: TaskSpec) -> str: ...

    def stream_events(self, task_id: str) -> AsyncGenerator[HarnessEvent, None]: ...

    async def send_message(self, task_id: str, message: str) -> None: ...

    async def get_result(self, task_id: str) -> HarnessResult: ...

    async def cancel(self, task_id: str) -> None: ...

    async def usage(self, task_id: str) -> Usage: ...


@runtime_checkable
class ModelProvider(Protocol):
    async def route(self, role: str, task: str) -> ModelChoice: ...

    async def complete(self, model: str, messages: list[ChatMessage]) -> Completion: ...

    async def budget(self, key: str) -> BudgetStatus: ...

    async def usage(self, key: str) -> Usage: ...


@runtime_checkable
class SandboxProvider(Protocol):
    async def create(self, spec: SandboxSpec) -> SandboxHandle: ...

    async def exec(self, sandbox_id: str, command: list[str]) -> ExecResult: ...

    async def fetch_branch(self, sandbox_id: str, branch: str) -> str: ...

    async def snapshot(self, sandbox_id: str) -> str | None: ...

    async def pause(self, sandbox_id: str) -> None: ...

    async def destroy(self, sandbox_id: str) -> None: ...

    async def usage(self, sandbox_id: str) -> Usage: ...


@runtime_checkable
class VcsProvider(Protocol):
    async def connect(self, user: str) -> None: ...

    async def list_repos(self, user: str) -> list[RepoRef]: ...

    async def create_repo(self, name: str) -> RepoRef | None: ...

    async def push_branch(self, repo: str, branch: str, sha: str) -> None: ...

    async def open_pr(self, repo: str, spec: PullRequestSpec) -> PullRequest: ...

    async def update_pr(self, repo: str, number: int, spec: PullRequestSpec) -> PullRequest: ...

    async def comment(self, repo: str, number: int, body: str) -> None: ...

    async def checks(self, repo: str, ref: str) -> list[CheckRun]: ...

    async def parse_webhook(self, headers: dict[str, str], body: bytes) -> WebhookEvent: ...


@runtime_checkable
class QualityGate(Protocol):
    def applies_to(self, repo: str, diff: str) -> bool: ...

    async def run(self, sandbox_id: str, context: GateContext) -> GateResult: ...


@runtime_checkable
class SkillSource(Protocol):
    async def list(self) -> list[SkillRef]: ...

    async def fetch(self, ref: str) -> SkillBundle: ...

    async def verify(self, ref: str) -> VerifyResult: ...


@runtime_checkable
class EvalRunner(Protocol):
    async def run(self, suite: str, version: str) -> EvalScores: ...

    async def compare(self, a: str, b: str) -> EvalComparison: ...


@runtime_checkable
class ObservabilityExporter(Protocol):
    async def export(self, item: ObservabilityItem) -> None: ...


@runtime_checkable
class AuthProvider(Protocol):
    async def authenticate(self, request: AuthRequest) -> Principal: ...


@runtime_checkable
class SecretsProvider(Protocol):
    async def get(self, ref: str) -> str: ...

    async def issue_short_lived(self, scope: str) -> str: ...


PROTOCOLS: dict[str, type[Any]] = {
    "Orchestrator": Orchestrator,
    "Storage": Storage,
    "IntakeSource": IntakeSource,
    "Notifier": Notifier,
    "Clarifier": Clarifier,
    "Planner": Planner,
    "HarnessAdapter": HarnessAdapter,
    "ModelProvider": ModelProvider,
    "SandboxProvider": SandboxProvider,
    "VcsProvider": VcsProvider,
    "QualityGate": QualityGate,
    "SkillSource": SkillSource,
    "EvalRunner": EvalRunner,
    "ObservabilityExporter": ObservabilityExporter,
    "AuthProvider": AuthProvider,
    "SecretsProvider": SecretsProvider,
}

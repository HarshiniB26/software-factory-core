"""Pydantic models for requests, plans, agents, skills, events, and manifests."""

import re
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

INTERFACE_MAJORS: dict[str, int] = {
    "Orchestrator": 1,
    "Storage": 1,
    "IntakeSource": 1,
    "Notifier": 1,
    "Clarifier": 1,
    "Planner": 1,
    "HarnessAdapter": 1,
    "ModelProvider": 1,
    "SandboxProvider": 1,
    "VcsProvider": 1,
    "QualityGate": 1,
    "SkillSource": 1,
    "EvalRunner": 1,
    "ObservabilityExporter": 1,
    "AuthProvider": 1,
    "SecretsProvider": 1,
}

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
_IMPLEMENTS = re.compile(r"^([A-Za-z][A-Za-z0-9]*)@(\d+)$")

RequestStatus = Literal[
    "created",
    "running",
    "parked",
    "awaiting_approval",
    "completed",
    "failed",
    "killed",
]
Risk = Literal["low", "medium", "high"]
AgentStatus = Literal["draft", "candidate", "canary", "active", "deprecated", "retired"]
FollowUpKind = Literal["new", "revise", "child"]


class Usage(BaseModel):
    usd: float = 0
    tokens: int = 0
    seconds: float = 0


class Attachment(BaseModel):
    name: str
    content_type: str = "text/plain"
    blob_key: str | None = None


class RequestCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)
    target: str | None = None
    requester: str = "local"
    overrides: dict[str, Any] = Field(default_factory=dict)


class FactoryRequest(BaseModel):
    id: UUID
    title: str
    body: str
    target: str | None = None
    requester: str
    status: RequestStatus
    created_at: datetime


class RequestDraft(BaseModel):
    title: str
    body: str
    target: str | None = None
    requester: str
    kind: FollowUpKind = "new"
    thread_id: str | None = None


class EventDraft(BaseModel):
    request_id: UUID
    type: str
    module: str | None = None
    config_hash: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class FactoryEvent(BaseModel):
    id: UUID
    request_id: UUID
    seq: int
    type: str
    module: str | None = None
    config_hash: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class Question(BaseModel):
    text: str
    options: list[str] = Field(default_factory=list)
    default: str | None = None


class Clarification(BaseModel):
    status: Literal["clear", "questions", "assumptions"]
    questions: list[Question] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    checks: list[str] = Field(default_factory=list)


class RepoContext(BaseModel):
    repo: str
    conventions: list[str] = Field(default_factory=list)


class Spec(BaseModel):
    request_id: UUID
    summary: str
    checks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class TaskStep(BaseModel):
    id: str
    goal: str
    depends_on: list[str] = Field(default_factory=list)
    touch: list[str] = Field(default_factory=list)
    checks: list[str] = Field(default_factory=list)
    risk: Risk = "low"


class TaskDAG(BaseModel):
    steps: list[TaskStep]
    risk: Risk = "low"


class Plan(BaseModel):
    id: UUID
    request_id: UUID
    version: int = 1
    summary: str
    dag: TaskDAG
    risk: Risk = "low"
    cost_estimate_usd: float = 0
    assumptions: list[str] = Field(default_factory=list)


class Approval(BaseModel):
    status: Literal["pending", "approved", "rejected"]
    plan_id: UUID


class AgentLineage(BaseModel):
    parent: str | None = None
    reason: str | None = None


class AgentTools(BaseModel):
    allow: list[str] = Field(default_factory=list)
    network: str = "registries-only"


class AgentModels(BaseModel):
    tier: str = "frontier-coding"
    harness: list[str] = Field(default_factory=list)
    reviewer_vendor: str | None = None


class AgentBudgets(BaseModel):
    usd: float = 8
    wall_minutes: int = 60


class AgentEvals(BaseModel):
    suite: str | None = None
    pass_rate: float | None = None
    cost_per_task_usd: float | None = None
    n: int | None = None


class AgentSpec(BaseModel):
    """Versioned agent definition. The registry stores these; it does not run them."""

    id: str
    version: str
    status: AgentStatus = "draft"
    lineage: AgentLineage = Field(default_factory=AgentLineage)
    capabilities: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    tools: AgentTools = Field(default_factory=AgentTools)
    models: AgentModels = Field(default_factory=AgentModels)
    budgets: AgentBudgets = Field(default_factory=AgentBudgets)
    evals: AgentEvals = Field(default_factory=AgentEvals)

    @field_validator("version")
    @classmethod
    def _semver(cls, value: str) -> str:
        if _SEMVER.match(value) is None:
            raise ValueError("version must be MAJOR.MINOR.PATCH")
        return value


class SkillSpec(BaseModel):
    id: str
    version: str
    source: str
    sha: str | None = None
    license: str
    description: str = ""

    @field_validator("version")
    @classmethod
    def _semver(cls, value: str) -> str:
        if _SEMVER.match(value) is None:
            raise ValueError("version must be MAJOR.MINOR.PATCH")
        return value


class SkillRef(BaseModel):
    ref: str
    license: str
    description: str = ""


class SkillBundle(BaseModel):
    ref: str
    content: str


class VerifyResult(BaseModel):
    ref: str
    ok: bool
    license: str
    findings: list[str] = Field(default_factory=list)


class ModuleManifest(BaseModel):
    id: str
    version: str
    implements: str
    capabilities: list[str] = Field(default_factory=list)
    config_schema: str | None = None
    secrets: list[str] = Field(default_factory=list)
    egress: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    healthcheck: str | None = None
    testing: Literal["in-process", "external"] = "in-process"

    @field_validator("version")
    @classmethod
    def _semver(cls, value: str) -> str:
        if _SEMVER.match(value) is None:
            raise ValueError("version must be MAJOR.MINOR.PATCH")
        return value

    @field_validator("implements")
    @classmethod
    def _implements(cls, value: str) -> str:
        match = _IMPLEMENTS.match(value)
        if match is None:
            raise ValueError("implements must be Interface@major")
        name, major = match.group(1), int(match.group(2))
        expected = INTERFACE_MAJORS.get(name)
        if expected is None:
            raise ValueError(f"unknown interface {name}")
        if major != expected:
            raise ValueError(f"{name} major must be {expected}")
        return value

    @property
    def interface_name(self) -> str:
        return self.implements.split("@", 1)[0]

    @property
    def interface_major(self) -> int:
        return int(self.implements.split("@", 1)[1])


class ResolvedConfig(BaseModel):
    modules: dict[str, str | list[str]]
    flags: dict[str, Any] = Field(default_factory=dict)
    budgets: dict[str, float] = Field(default_factory=dict)
    module_config: dict[str, dict[str, Any]] = Field(default_factory=dict)
    config_hash: str
    layers_applied: list[str]


class RepoRef(BaseModel):
    owner: str
    name: str
    host: str = "github.com"

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


class PullRequestSpec(BaseModel):
    title: str
    body: str = ""
    head: str
    base: str = "main"


class PullRequest(BaseModel):
    repo: str
    number: int
    title: str
    url: str
    head: str
    base: str


class PullRequestRef(BaseModel):
    repo: str
    number: int
    url: str


class CheckRun(BaseModel):
    name: str
    status: Literal["queued", "in_progress", "completed"]
    conclusion: Literal["success", "failure", "neutral", "cancelled"] | None = None


class WebhookEvent(BaseModel):
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)


class SandboxSpec(BaseModel):
    image: str = "fake"
    repo: str | None = None


class SandboxHandle(BaseModel):
    id: str


class ExecResult(BaseModel):
    exit_code: int
    stdout: str = ""
    stderr: str = ""


class TaskSpec(BaseModel):
    instruction: str
    repo: str | None = None


class HarnessCapabilities(BaseModel):
    streaming: bool = True
    worktrees: bool = False
    name: str = "fake"


class HarnessEvent(BaseModel):
    type: str
    message: str


class HarnessResult(BaseModel):
    status: Literal["ok", "failed", "cancelled"]
    summary: str


class ThreadMessage(BaseModel):
    id: UUID
    request_id: UUID
    role: Literal["user", "assistant", "system"]
    kind: Literal["text", "question", "plan", "progress", "pr", "assumption"]
    body: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ModelChoice(BaseModel):
    model: str
    role: str


class Completion(BaseModel):
    model: str
    text: str


class BudgetStatus(BaseModel):
    key: str
    limit_usd: float
    spent_usd: float


class GateContext(BaseModel):
    repo: str
    diff: str = ""
    workspace: str | None = None


class GateResult(BaseModel):
    verdict: Literal["pass", "fail"]
    findings: list[str] = Field(default_factory=list)


class EvalScores(BaseModel):
    suite: str
    version: str
    pass_rate: float
    n: int


class EvalComparison(BaseModel):
    a: str
    b: str
    pass_rate_delta: float


class ObservabilityItem(BaseModel):
    kind: Literal["event", "span", "metric"]
    name: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class AuthRequest(BaseModel):
    headers: dict[str, str] = Field(default_factory=dict)


class Principal(BaseModel):
    id: str
    roles: list[Literal["requester", "approver", "admin"]]

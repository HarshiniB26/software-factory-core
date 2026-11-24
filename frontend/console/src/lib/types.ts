export type Principal = { id: string; roles: string[] };

export type Repo = {
  owner: string;
  name: string;
  full_name: string;
  description: string;
  path: string | null;
  kind: "local" | "fixture" | "github";
  private?: boolean;
  default_branch?: string | null;
  branch?: string | null;
};

export type GitHubAccount = {
  login: string;
  avatar_url: string;
  installed: boolean;
};

export type RepoList = {
  repos: Repo[];
  connected: Repo | null;
  mode: string;
  oauth: boolean;
  github: GitHubAccount | null;
  install_url: string | null;
};

export type RequestRow = {
  id: string;
  title: string;
  body: string;
  target: string | null;
  requester: string;
  status: string;
  created_at: string;
};

export type ThreadMessage = {
  id: string;
  role: string;
  kind: string;
  body: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type RunEvent = {
  id: string;
  type: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type Pull = {
  url: string;
  number: number;
  title?: string;
  head?: string;
  base?: string;
  body?: string;
  repo?: string;
  risk?: string;
  request_id?: string;
};

export type GateReport = { verdict?: string; findings?: string[]; gate?: string };

export type CrewMember = {
  id: string;
  role: string;
  harness: string;
  model: string;
  status: string;
  tokens: number;
  usd: number;
  seconds: number;
};

export type RepoFile = {
  path: string;
  status: string;
  original: string;
  modified: string;
};

export type PlanStep = {
  id?: string;
  goal?: string;
  depends_on?: string[];
  touch?: string[];
};

export type RunView = {
  request: RequestRow;
  messages: ThreadMessage[];
  events: RunEvent[];
  diff: string;
  diff_kind: "fixture" | "git";
  gates: GateReport[];
  agent: { id?: string; version?: string; status?: string } | null;
  prs: Pull[];
  risk: string;
  risk_score: number;
  assumptions: string[];
  questions: { text?: string; options?: string[]; default?: string }[];
  stage: string | null;
  steps: PlanStep[];
  crew: CrewMember[];
  logs: Array<string | { group: string; calls: { tool: string; text: string }[] }>;
  files: RepoFile[];
};

export type RoleSetting = { harness: string; model: string };

export type WorkspaceSettings = {
  plan_approval: string;
  roles: Record<string, RoleSetting>;
};

export type AgentCard = {
  id: string;
  version: string;
  status: string;
  parent?: string;
  pass_rate?: number;
  n?: number;
  cost_per_task_usd?: number;
  promotions?: { version: string; result: string; reason: string }[];
};

export type CostPoint = {
  date: string;
  usd: number;
  completed: number;
  failed: number;
  running: number;
  parked: number;
  other: number;
  success_rate: number;
  average_duration_seconds: number;
};

export type CostReport = {
  pull_requests: number;
  estimated_usd: number;
  series: CostPoint[];
  success_rate: number;
  average_duration_seconds: number;
  by_role: { role: string; usd: number }[];
};

export type BoardCard = {
  id: string;
  title: string;
  status: string;
  stage: string;
  target: string | null;
  created_at: string;
  cost_usd: number;
  duration_seconds: number;
  model: string | null;
};

export type InboxItem = RequestRow & { question?: string; kind?: string };

export class ApiError extends Error {
  status: number;

  constructor(status: number, detail: string) {
    super(detail || `Request failed (${status})`);
    this.status = status;
  }
}

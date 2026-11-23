export type Principal = { id: string; roles: string[] };

export type Repo = {
  owner: string;
  name: string;
  full_name: string;
  description: string;
  path: string | null;
  kind: "local" | "fixture" | "github";
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
};

export class ApiError extends Error {
  status: number;

  constructor(status: number, detail: string) {
    super(detail || `Request failed (${status})`);
    this.status = status;
  }
}

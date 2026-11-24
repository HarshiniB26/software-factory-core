import type { paths } from "./schema";
import createClient from "openapi-fetch";
import {
  ApiError,
  type AgentCard,
  type CostReport,
  type Principal,
  type Repo,
  type RequestRow,
  type RunView,
  type BoardCard,
  type InboxItem,
  type WorkspaceSettings,
} from "./types";

const raw = createClient<paths>({ baseUrl: "/api" });

function authHeaders(): Headers {
  const headers = new Headers();
  const token = localStorage.getItem("factory_token");
  if (token) headers.set("authorization", `Bearer ${token}`);
  return headers;
}

async function unwrap<T>(pending: Promise<{ data?: unknown; error?: unknown; response: Response }>): Promise<T> {
  const result = await pending;
  if (result.response.ok && result.data !== undefined) return result.data as T;
  let detail = result.response.statusText;
  if (result.error && typeof result.error === "object" && "detail" in result.error) {
    detail = String((result.error as { detail: unknown }).detail);
  }
  throw new ApiError(result.response.status, detail);
}

export const api = {
  me: () => unwrap<Principal>(raw.GET("/auth/me", { headers: authHeaders() })),
  login: async (user: string, role: string) => {
    const session = await unwrap<{ token: string; user: string; role: string }>(
      raw.POST("/auth/dev-login", {
        body: { user, role },
        headers: authHeaders(),
      }),
    );
    localStorage.setItem("factory_token", session.token);
    return session;
  },
  repos: () =>
    unwrap<{ repos: Repo[]; connected: Repo | null; mode: string; oauth: boolean }>(
      raw.GET("/repos", { headers: authHeaders() }),
    ),
  connect: (fullName: string) =>
    unwrap<Repo>(
      raw.POST("/repos/connect", {
        body: { full_name: fullName },
        headers: authHeaders(),
      }),
    ),
  createRequest: (title: string, body: string, target: string | null) =>
    unwrap<RequestRow>(
      raw.POST("/requests", {
        body: { title, body, target, requester: "local" },
        headers: authHeaders(),
      }),
    ),
  requests: () => unwrap<RequestRow[]>(raw.GET("/requests", { headers: authHeaders() })),
  request: (id: string) => unwrap<RequestRow>(raw.GET("/requests/{request_id}", { params: { path: { request_id: id } }, headers: authHeaders() })),
  view: (id: string) =>
    unwrap<RunView>(
      raw.GET("/requests/{request_id}/view", {
        params: { path: { request_id: id } },
        headers: authHeaders(),
      }),
    ),
  answer: (id: string, text: string) =>
    unwrap(raw.POST("/requests/{request_id}/answers", { params: { path: { request_id: id } }, body: { text }, headers: authHeaders() })),
  decide: (id: string, decision: "approve" | "reject") =>
    unwrap(
      raw.POST("/requests/{request_id}/decision", {
        params: { path: { request_id: id } },
        body: { decision },
        headers: authHeaders(),
      }),
    ),
  inbox: () => unwrap<{ items: InboxItem[] }>(raw.GET("/inbox", { headers: authHeaders() })),
  board: () => unwrap<{ items: BoardCard[] }>(raw.GET("/board", { headers: authHeaders() })),
  prs: () => unwrap<{ items: { url: string; risk: string; number: number; request_id: string; title?: string; head?: string; base?: string; repo?: string }[] }>(raw.GET("/prs", { headers: authHeaders() })),
  modules: () =>
    unwrap<{
      installed: { id: string; version: string; implements: string }[];
      selected: Record<string, string | string[]>;
      flags: Record<string, unknown>;
    }>(raw.GET("/modules", { headers: authHeaders() })),
  agents: () =>
    unwrap<{ agents: { id: string; version: string; status: string; capabilities: string[] }[] }>(
      raw.GET("/registry/agents", { headers: authHeaders() }),
    ),
  skills: () =>
    unwrap<{ skills: { id: string; version: string; license: string }[] }>(
      raw.GET("/registry/skills", { headers: authHeaders() }),
    ),
  cost: () => unwrap<CostReport>(raw.GET("/cost", { headers: authHeaders() })),
  settings: () => unwrap<WorkspaceSettings>(raw.GET("/settings", { headers: authHeaders() })),
  saveSettings: (body: WorkspaceSettings) =>
    unwrap<WorkspaceSettings>(raw.PUT("/settings", { body, headers: authHeaders() })),
  promote: (id: string, version: string) =>
    unwrap<{ allowed: boolean; reason: string }>(
      raw.POST("/registry/promote", { body: { id, version }, headers: authHeaders() }),
    ),
  catalog: () =>
    unwrap<{ agents: { id: string; version: string; status: string; capabilities: string[] }[]; catalog: AgentCard[] }>(
      raw.GET("/registry/agents", { headers: authHeaders() }),
    ),
  audit: () =>
    unwrap<{ events: { type: string; created_at: string; request_id: string }[]; kill_switch: boolean }>(
      raw.GET("/audit", { headers: authHeaders() }),
    ),
  kill: () => unwrap<{ on: boolean }>(raw.POST("/admin/kill", { headers: authHeaders() })),
  resume: () => unwrap<{ on: boolean }>(raw.POST("/admin/resume", { headers: authHeaders() })),
  newApp: (name: string, description: string) =>
    unwrap<{ id: string }>(raw.POST("/apps/new", { body: { name, description }, headers: authHeaders() })),
};

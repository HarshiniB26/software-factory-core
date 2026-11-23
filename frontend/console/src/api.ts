const base = "/api";

export type Principal = { id: string; roles: string[] };

async function send<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem("factory_token");
  const headers = new Headers(init?.headers);
  if (token) headers.set("authorization", `Bearer ${token}`);
  if (init?.body && !headers.has("content-type")) headers.set("content-type", "application/json");
  const response = await fetch(`${base}${path}`, { ...init, headers });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

export const api = {
  me: () => send<Principal>("/auth/me"),
  login: (user: string, role: string) =>
    send<{ token: string }>("/auth/dev-login", {
      method: "POST",
      body: JSON.stringify({ user, role }),
    }),
  repos: () => send<{ repos: { full_name: string }[]; mode: string }>("/repos"),
  createRequest: (title: string, body: string, target: string | null) =>
    send<{ id: string }>("/requests", {
      method: "POST",
      body: JSON.stringify({ title, body, target }),
    }),
  requests: () => send<{ id: string; title: string; status: string; target: string | null }[]>("/requests"),
  transcript: (id: string) =>
    send<{ messages: { id: string; role: string; kind: string; body: string; payload: Record<string, unknown> }[] }>(
      `/requests/${id}/transcript`,
    ),
  answer: (id: string, text: string) =>
    send(`/requests/${id}/answers`, { method: "POST", body: JSON.stringify({ text }) }),
  decide: (id: string, decision: string) =>
    send(`/requests/${id}/decision`, { method: "POST", body: JSON.stringify({ decision }) }),
  follow: (id: string, message: string) =>
    send<{ id: string; kind: string }>(`/requests/${id}/follow-ups`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  inbox: () => send<{ items: { id: string; title: string; status: string }[] }>("/inbox"),
  prs: () =>
    send<{ items: { url: string; title?: string; risk: string; request_id: string; number: number }[] }>("/prs"),
  modules: () =>
    send<{ installed: { id: string; version: string; implements: string }[]; flags: Record<string, unknown> }>(
      "/modules",
    ),
  agents: () => send<{ agents: { id: string; version: string; status: string; capabilities: string[] }[] }>(
    "/registry/agents",
  ),
  skills: () => send<{ skills: { id: string; version: string; license: string }[] }>("/registry/skills"),
  cost: () => send<{ pull_requests: number; estimated_usd: number }>("/cost"),
  audit: () => send<{ events: { type: string; created_at: string; request_id: string }[] }>("/audit"),
  kill: () => send("/admin/kill", { method: "POST" }),
  resume: () => send("/admin/resume", { method: "POST" }),
  newApp: (name: string, description: string) =>
    send<{ id: string }>("/apps/new", { method: "POST", body: JSON.stringify({ name, description }) }),
};

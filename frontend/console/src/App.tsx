import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useLocalRuntime,
  type ChatModelAdapter,
} from "@assistant-ui/react";
import type { UIMessage } from "ai";
import { useEffect, useState } from "react";
import { api } from "./api";

type Page = "chat" | "runs" | "inbox" | "prs" | "modules" | "registry" | "cost" | "audit";

const adapter: ChatModelAdapter = {
  async run({ messages }) {
    const last = messages.at(-1);
    const text = last?.content.find((part) => part.type === "text");
    const body = text && "text" in text ? text.text : "Add a health check";
    const target = localStorage.getItem("factory_repo");
    const created = await api.createRequest(body.slice(0, 80), body, target);
    const transcript = await waitForCard(created.id);
    const reply = transcript.messages.filter((message) => message.role === "assistant").at(-1);
    const content = reply?.body || "Working.";
    // UIMessage is the AI SDK shape the console would stream in a later transport.
    const _typed: UIMessage["role"] = "assistant";
    void _typed;
    return { content: [{ type: "text" as const, text: content }] };
  },
};

async function waitForCard(id: string) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const transcript = await api.transcript(id);
    if (transcript.messages.some((message) => message.kind === "pr" || message.kind === "question")) {
      return transcript;
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  return api.transcript(id);
}

export function App() {
  const [page, setPage] = useState<Page>("chat");
  const [user, setUser] = useState("local");
  useEffect(() => {
    api.me().then((principal) => setUser(principal.id)).catch(() => setUser("signed out"));
  }, []);
  return (
    <div className="app">
      <nav>
        <strong>Factory</strong>
        <p>{user}</p>
        {(["chat", "runs", "inbox", "prs", "modules", "registry", "cost", "audit"] as Page[]).map((item) => (
          <button key={item} className={page === item ? "active" : ""} onClick={() => setPage(item)}>
            {item}
          </button>
        ))}
      </nav>
      <main>
        {page === "chat" && <Chat />}
        {page === "runs" && <Runs />}
        {page === "inbox" && <Inbox />}
        {page === "prs" && <Pulls />}
        {page === "modules" && <Modules />}
        {page === "registry" && <Registry />}
        {page === "cost" && <Cost />}
        {page === "audit" && <Audit />}
      </main>
    </div>
  );
}

function Chat() {
  const runtime = useLocalRuntime(adapter);
  const [repos, setRepos] = useState<string[]>([]);
  const [name, setName] = useState("ada");
  useEffect(() => {
    api.repos().then((payload) => setRepos(payload.repos.map((repo) => repo.full_name))).catch(() => setRepos([]));
  }, []);
  return (
    <section>
      <div className="row">
        <input value={name} onChange={(event) => setName(event.target.value)} />
        <button
          onClick={async () => {
            const session = await api.login(name, "approver");
            localStorage.setItem("factory_token", session.token);
          }}
        >
          Sign in
        </button>
        <select
          onChange={(event) => localStorage.setItem("factory_repo", event.target.value)}
          defaultValue="factory/demo"
        >
          <option value="factory/demo">factory/demo</option>
          {repos.map((repo) => (
            <option key={repo}>{repo}</option>
          ))}
        </select>
      </div>
      <AssistantRuntimeProvider runtime={runtime}>
        <ThreadPrimitive.Root className="card">
          <ThreadPrimitive.Viewport>
            <ThreadPrimitive.Messages
              components={{
                UserMessage: () => (
                  <div className="bubble user">
                    <MessagePrimitive.Content />
                  </div>
                ),
                AssistantMessage: () => (
                  <div className="bubble assistant">
                    <MessagePrimitive.Content />
                  </div>
                ),
              }}
            />
          </ThreadPrimitive.Viewport>
          <ComposerPrimitive.Root className="row">
            <ComposerPrimitive.Input placeholder="Describe the change" />
            <ComposerPrimitive.Send>Send</ComposerPrimitive.Send>
          </ComposerPrimitive.Root>
        </ThreadPrimitive.Root>
      </AssistantRuntimeProvider>
    </section>
  );
}

function Runs() {
  const [rows, setRows] = useState<{ id: string; title: string; status: string }[]>([]);
  useEffect(() => {
    api.requests().then(setRows).catch(() => setRows([]));
  }, []);
  return (
    <section>
      <h1>Runs</h1>
      {rows.map((row) => (
        <article key={row.id} className="card">
          <strong>{row.title}</strong>
          <div>{row.status}</div>
        </article>
      ))}
    </section>
  );
}

function Inbox() {
  const [rows, setRows] = useState<{ id: string; title: string; status: string }[]>([]);
  useEffect(() => {
    api.inbox().then((payload) => setRows(payload.items)).catch(() => setRows([]));
  }, []);
  return (
    <section>
      <h1>Needs you</h1>
      {rows.map((row) => (
        <article key={row.id} className="card">
          <strong>{row.title}</strong>
          <div>{row.status}</div>
          {row.status === "parked" && (
            <button onClick={() => api.answer(row.id, "smallest change")}>Use default</button>
          )}
          {row.status === "awaiting_approval" && (
            <button onClick={() => api.decide(row.id, "approve")}>Approve plan</button>
          )}
        </article>
      ))}
    </section>
  );
}

function Pulls() {
  const [rows, setRows] = useState<{ url: string; risk: string; number: number }[]>([]);
  useEffect(() => {
    api.prs().then((payload) => setRows(payload.items)).catch(() => setRows([]));
  }, []);
  return (
    <section>
      <h1>Pull requests</h1>
      <p>The factory opens these and stops. A human merges.</p>
      {rows.map((row) => (
        <article key={row.url} className="card">
          <a href={row.url}>{row.url}</a>
          <div>risk {row.risk}</div>
        </article>
      ))}
    </section>
  );
}

function Modules() {
  const [rows, setRows] = useState<{ id: string; version: string; implements: string }[]>([]);
  useEffect(() => {
    api.modules().then((payload) => setRows(payload.installed)).catch(() => setRows([]));
  }, []);
  return (
    <section>
      <h1>Modules</h1>
      {rows.map((row) => (
        <article key={row.id} className="card">
          {row.id} {row.version} · {row.implements}
        </article>
      ))}
    </section>
  );
}

function Registry() {
  const [agents, setAgents] = useState<{ id: string; version: string; status: string }[]>([]);
  useEffect(() => {
    api.agents().then((payload) => setAgents(payload.agents)).catch(() => setAgents([]));
  }, []);
  return (
    <section>
      <h1>Registry</h1>
      <p>Worker agents are assembled per run. Nothing here is a predefined coder.</p>
      {agents.map((agent) => (
        <article key={`${agent.id}@${agent.version}`} className="card">
          {agent.id}@{agent.version} · {agent.status}
        </article>
      ))}
      <button onClick={() => api.newApp("demo-app", "A small service with a health check.")}>New app</button>
    </section>
  );
}

function Cost() {
  const [cost, setCost] = useState<{ pull_requests: number; estimated_usd: number } | null>(null);
  useEffect(() => {
    api.cost().then(setCost).catch(() => setCost(null));
  }, []);
  return (
    <section>
      <h1>Cost</h1>
      <article className="card">
        {cost ? `${cost.pull_requests} pull requests, about $${cost.estimated_usd}` : "No spend yet."}
      </article>
    </section>
  );
}

function Audit() {
  const [events, setEvents] = useState<{ type: string; created_at: string }[]>([]);
  useEffect(() => {
    api.audit().then((payload) => setEvents(payload.events)).catch(() => setEvents([]));
  }, []);
  return (
    <section>
      <h1>Audit</h1>
      <button onClick={() => api.kill()}>Kill switch</button>
      <button onClick={() => api.resume()}>Resume</button>
      {events.map((event, index) => (
        <article key={`${event.type}-${index}`} className="card">
          {event.type} · {event.created_at}
        </article>
      ))}
    </section>
  );
}

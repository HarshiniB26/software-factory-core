import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import { compactGoal, eventLabel, formatWhen, isFixturePublish, money, pullHref, statusTone } from "@/lib/format";
import type { PlanStep, RepoFile, RunView } from "@/lib/types";
import { DiffEditor, type DiffOnMount } from "@monaco-editor/react";
import { motion } from "framer-motion";
import { Background, Handle, Position, ReactFlow, type Edge, type Node } from "@xyflow/react";
import { GitPullRequest, ListChecks, Loader2, Search, SquarePen, TerminalSquare } from "lucide-react";
import { useRef } from "react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

const TERMINAL = new Set(["completed", "failed", "killed", "parked", "awaiting_approval"]);

export function RunPanel({ id, showTitle = false }: { id: string; showTitle?: boolean }) {
  const [view, setView] = useState<RunView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shown, setShown] = useState(1);
  const [file, setFile] = useState<string>("");
  const [cursor, setCursor] = useState(-1);
  const [focus, setFocus] = useState<string | null>(null);
  const { theme } = useTheme();

  useEffect(() => {
    let stop = false;
    async function poll() {
      try {
        const next = await api.view(id);
        if (stop) return;
        setView(next);
        setError(null);
        setFile((current) => current || next.files.find((item) => item.status === "modified")?.path || next.files[0]?.path || "");
        if (!TERMINAL.has(next.request.status)) window.setTimeout(poll, 500);
      } catch (err) {
        if (!stop) setError(err instanceof Error ? err.message : "Could not load this run");
      }
    }
    void poll();
    return () => {
      stop = true;
    };
  }, [id]);

  useEffect(() => {
    if (!view) return;
    const total = Math.max(view.steps.length, 1);
    if (cursor >= total) return;
    const timer = window.setTimeout(() => setCursor((count) => count + 1), cursor < 0 ? 800 : 1100);
    return () => window.clearTimeout(timer);
  }, [cursor, view]);

  useEffect(() => {
    if (!view || shown >= view.events.length) return;
    const timer = window.setTimeout(() => setShown((count) => count + 1), 90);
    return () => window.clearTimeout(timer);
  }, [shown, view]);

  const selected = useMemo(() => view?.files.find((item) => item.path === file) ?? view?.files[0], [view, file]);

  if (error) return <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>;
  if (!view) {
    return (
      <div className="space-y-3">
        <div className="h-8 w-40 animate-pulse rounded-full bg-zinc-200 dark:bg-zinc-800" />
        <div className="h-28 animate-pulse rounded-xl bg-zinc-200 dark:bg-zinc-800" />
        <div className="h-40 animate-pulse rounded-xl bg-zinc-200 dark:bg-zinc-800" />
      </div>
    );
  }

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      {showTitle ? <h1 className="text-xl font-semibold tracking-tight">{view.request.title}</h1> : null}
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={statusTone(view.request.status)}>{view.request.status.replaceAll("_", " ")}</Badge>
        <span className="text-xs text-zinc-500">Risk {view.risk} · score {view.risk_score}</span>
        {!TERMINAL.has(view.request.status) ? <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-400" /> : null}
      </div>
      <Questions view={view} id={id} />
      <Dag steps={view.steps.length ? view.steps : [{ id: "implement", goal: view.request.body }]} cursor={cursor} />
      <Crew view={view} focus={focus} onFocus={setFocus} />
      <Log events={view.events.slice(0, shown)} logs={view.logs} />
      <Files files={view.files} selected={selected} file={file} onPick={setFile} dark={theme === "dark"} />
      <Gates view={view} />
      <Pulls view={view} id={id} />
    </motion.div>
  );
}

function Questions({ view, id }: { view: RunView; id: string }) {
  if (view.request.status === "parked" && view.questions.length > 0) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950">
        {view.questions.map((question) => (
          <div key={question.text}>
            <p className="text-sm font-medium">{question.text}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {(question.options ?? []).map((option) => (
                <Button key={option} size="sm" variant="secondary" onClick={() => act(() => api.answer(id, option), "Answer sent")}>
                  {option}
                </Button>
              ))}
            </div>
          </div>
        ))}
      </section>
    );
  }
  if (view.request.status === "awaiting_approval") {
    return (
      <div className="flex gap-2">
        <Button size="sm" onClick={() => act(() => api.decide(id, "approve"), "Plan approved")}>Approve plan</Button>
        <Button size="sm" variant="secondary" onClick={() => act(() => api.decide(id, "reject"), "Plan rejected")}>Reject</Button>
      </div>
    );
  }
  return null;
}

const nodeTypes = { task: StepNode };

function Dag({ steps, cursor }: { steps: PlanStep[]; cursor: number }) {
  const nodes: Node[] = steps.map((step, index) => {
    const column = depth(step, steps);
    const row = steps.filter((item, itemIndex) => depth(item, steps) === column && itemIndex <= index).length - 1;
    const status = index < cursor ? "done" : index === cursor ? "live" : "waiting";
    return {
      id: step.id ?? `step-${index}`,
      position: { x: column * 280, y: row * 130 },
      data: { label: step.id, goal: compactGoal(step.goal ?? ""), status, worktree: (step.touch ?? [])[0] },
      type: "task",
      width: 200,
      height: 84,
    };
  });
  const edges: Edge[] = steps.flatMap((step) =>
    (step.depends_on ?? []).map((source) => ({
      id: `${source}-${step.id}`,
      source,
      target: step.id ?? source,
      animated: true,
      type: "smoothstep",
      style: { stroke: "#0c6e62", strokeWidth: 2 },
    })),
  );
  const caption = cursor < 0 ? "Queued" : cursor >= steps.length ? "Plan finished" : `Running ${steps[cursor]?.id ?? "step"}`;
  return (
    <section className="surface flex h-80 flex-col overflow-hidden rounded-2xl">
      <p className="px-4 pt-3 text-sm font-medium text-[var(--accent)]">{caption}</p>
      <div className="min-h-0 flex-1">
      <ReactFlow
        style={{ width: "100%", height: "100%" }}
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        onlyRenderVisibleElements={false}
        nodesDraggable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background />
      </ReactFlow>
      </div>
    </section>
  );
}

function depth(step: PlanStep, steps: PlanStep[]): number {
  const parents = step.depends_on ?? [];
  if (parents.length === 0) return 0;
  return 1 + Math.max(...parents.map((id) => depth(steps.find((item) => item.id === id) ?? { id }, steps)));
}

function StepNode({ data }: { data: { label?: string; goal?: string; status?: string; worktree?: string } }) {
  const live = data.status === "live";
  const done = data.status === "done";
  return (
    <div className={`w-48 rounded-xl border px-3 py-2 text-xs shadow-md ${live ? "border-[var(--accent)] bg-white dark:bg-zinc-950" : done ? "border-[var(--accent)]/40 bg-white/95 dark:bg-zinc-900" : "border-transparent bg-white/80 dark:bg-zinc-900"}`}>
      <Handle type="target" position={Position.Left} />
      <div className="flex items-center justify-between">
        <span className="font-medium">{data.label}</span>
        <span className={`rounded-full px-1.5 py-0.5 text-[10px] uppercase ${live ? "animate-pulse bg-[var(--accent)] text-white" : done ? "bg-[var(--good)] text-white" : "bg-zinc-200 text-zinc-500"}`}>{live ? "running" : done ? "done" : "waiting"}</span>
      </div>
      <p className="mt-1 text-zinc-500">{data.goal}</p>
      {data.worktree ? <p className="mt-1 text-[10px] uppercase tracking-wide text-[var(--accent-2)]">worktree {data.worktree}</p> : null}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

function Crew({ view, focus, onFocus }: { view: RunView; focus: string | null; onFocus: (role: string | null) => void }) {
  const people = view.crew.length
    ? view.crew
    : [{ id: "implement", role: "implementer", harness: "claude-code", model: "claude-sonnet", status: "ok", tokens: 1200, usd: 0.02, seconds: 4 }];
  const selected = people.find((person) => person.role === focus);
  return (
    <div>
      <div className="grid gap-2 md:grid-cols-3">
        {people.map((person, index) => {
          const live = person.status !== "ok";
          return (
          <button key={`${person.id}-${index}`} className="surface rounded-2xl p-3 text-left" onClick={() => onFocus(person.role)}>
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 text-sm font-medium capitalize">
                <HarnessMark harness={person.harness} model={person.model} />
                <span>
                  <span className="flex items-center gap-1.5">
                    <RoleIcon role={person.role} />
                    {person.role}
                  </span>
                  <span className="mt-0.5 block text-xs font-normal text-zinc-500">{person.harness}</span>
                </span>
              </span>
              <span className="flex items-center gap-1 text-xs text-[var(--good)]">
                <span className={`h-2 w-2 rounded-full bg-[var(--good)] ${live ? "animate-pulse" : ""}`} />
                {person.status}
              </span>
            </div>
            <p className="mt-2 text-xs text-zinc-500">{person.model}</p>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
              <div className="h-full bg-[var(--accent)]" style={{ width: person.status === "ok" ? "100%" : "55%" }} />
            </div>
            <p className="mt-2 text-xs text-zinc-500">{person.tokens} tokens · {money(person.usd)} · {person.seconds}s</p>
          </button>
          );
        })}
      </div>
      {selected ? (
        <div className="surface mt-2 rounded-2xl p-3 text-sm">
          <div className="flex items-center justify-between">
            <p className="font-medium capitalize">{selected.role} transcript</p>
            <button className="text-xs underline" onClick={() => onFocus(null)}>Close</button>
          </div>
          <p className="mt-2 text-zinc-500">Harness {selected.harness}. Model {selected.model}.</p>
          <ul className="mt-2 space-y-1 font-mono text-xs">
            {callsFor(view, selected.role).map((call, index) => (
              <li key={`${call.tool}-${index}`}><span className={toolColor(call.tool)}>{call.tool}</span> {call.text}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function HarnessMark({ harness, model }: { harness: string; model: string }) {
  const claude = harness.includes("claude") || model.includes("claude");
  const openai = harness.includes("codex") || model.startsWith("gpt");
  const letter = claude ? "C" : openai ? "G" : "A";
  const color = claude ? "bg-[#d97757]" : openai ? "bg-[#10a37f]" : "bg-[var(--accent)]";
  return <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg text-xs font-semibold text-white ${color}`}>{letter}</span>;
}

function RoleIcon({ role }: { role: string }) {
  if (role === "researcher") return <Search className="h-3.5 w-3.5 text-[var(--accent)]" />;
  if (role === "tester") return <ListChecks className="h-3.5 w-3.5 text-[var(--accent)]" />;
  if (role === "reviewer") return <TerminalSquare className="h-3.5 w-3.5 text-[var(--accent-2)]" />;
  return <SquarePen className="h-3.5 w-3.5 text-[var(--accent)]" />;
}

function Log({ events, logs }: { events: RunView["events"]; logs: RunView["logs"] }) {
  const groups = normalizeLogs(logs);
  return (
    <section className="rounded-2xl border border-zinc-800 bg-zinc-950 p-3 text-zinc-100">
      <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">Terminal</p>
      <div className="mt-2 space-y-2">
        {groups.map((group) => (
          <details key={group.key} open className="rounded-lg bg-white/5 px-2 py-1">
            <summary className="cursor-pointer text-xs text-zinc-300">{group.group}</summary>
            <ul className="mt-1 space-y-1">
              {group.calls.map((call, index) => (
                <li key={`${group.group}-${index}`} className="font-mono text-[11px]">
                  <span className={toolColor(call.tool)}>{call.tool}</span> {call.text}
                </li>
              ))}
            </ul>
          </details>
        ))}
      </div>
      <ol className="mt-2 space-y-1 font-mono text-[11px]">
        {events.slice(-4).map((event) => (
          <li key={event.id} className="text-zinc-500">{formatWhen(event.created_at)} {eventLabel(event.type)}</li>
        ))}
      </ol>
    </section>
  );
}

function toolColor(tool: string) {
  if (tool === "read") return "text-sky-300";
  if (tool === "edit") return "text-amber-300";
  return "text-emerald-300";
}

function normalizeLogs(logs: RunView["logs"]) {
  const groups: { key: string; group: string; calls: { tool: string; text: string }[] }[] = [];
  const loose: { tool: string; text: string }[] = [];
  logs.forEach((entry, index) => {
    if (typeof entry === "string") {
      loose.push({ tool: "bash", text: entry });
      return;
    }
    groups.push({ key: `${entry.group}-${index}`, group: entry.group, calls: entry.calls });
  });
  if (loose.length) groups.push({ key: "session", group: "session", calls: loose });
  return groups;
}

function callsFor(view: RunView, role: string) {
  const group = normalizeLogs(view.logs).find((item) => item.group.startsWith(role.slice(0, 4))) ?? normalizeLogs(view.logs)[0];
  return group?.calls ?? [];
}

function Files({
  files,
  selected,
  file,
  onPick,
  dark,
}: {
  files: RepoFile[];
  selected: RepoFile | undefined;
  file: string;
  onPick: (path: string) => void;
  dark: boolean;
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
      <ul className="flex gap-1 overflow-auto border-b border-zinc-200 bg-zinc-50 px-2 py-1 text-xs dark:border-zinc-800 dark:bg-zinc-900">
        {files.map((item) => (
          <li key={item.path}>
            <button
              className={`whitespace-nowrap rounded px-2 py-1 ${item.path === (selected?.path ?? file) ? "bg-white font-medium dark:bg-zinc-950" : ""}`}
              onClick={() => onPick(item.path)}
            >
              {item.path}
            </button>
          </li>
        ))}
        {files.length === 0 ? <li className="px-2 py-3 text-zinc-400">No files yet.</li> : null}
      </ul>
      {selected ? <SafeDiff selected={selected} dark={dark} /> : <p className="p-4 text-sm text-zinc-500">Pick a file.</p>}
    </section>
  );
}

function Gates({ view }: { view: RunView }) {
  if (!view.gates.length) return null;
  return (
    <div className="grid gap-2 md:grid-cols-3">
      {view.gates.map((gate) => (
        <article key={gate.gate} className="rounded-xl border border-zinc-200 p-3 dark:border-zinc-800">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">{gate.gate}</p>
            <Badge tone={gate.verdict === "fail" ? "bad" : "ok"}>{gate.verdict}</Badge>
          </div>
          <ul className="mt-2 space-y-1 text-xs text-zinc-500">
            {(gate.findings ?? ["No findings"]).map((finding) => (
              <li key={finding}>{finding}</li>
            ))}
          </ul>
        </article>
      ))}
    </div>
  );
}

function Pulls({ view, id }: { view: RunView; id: string }) {
  if (!view.prs.length) return null;
  return (
    <div className="space-y-2">
      {view.prs.map((pull) => {
        const href = pullHref(pull.url, id);
        const local = isFixturePublish(pull.url);
        return (
          <section key={pull.url} className="rounded-xl border border-zinc-200 p-3 dark:border-zinc-800">
            <div className="flex items-center gap-2">
              <GitPullRequest className="h-4 w-4 text-emerald-600" />
              <p className="text-sm font-medium">Pull request #{pull.number}</p>
              <Badge tone="ok">open</Badge>
            </div>
            <p className="mt-1 text-xs text-zinc-500">{pull.head} → {pull.base ?? "main"} · {pull.repo}</p>
            <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">A person merges this pull request. The factory does not.</p>
            {local ? (
              <Link to={href} className="mt-2 inline-flex text-sm font-medium underline">Review in this run</Link>
            ) : (
              <a href={href} className="mt-2 inline-flex text-sm font-medium underline" target="_blank" rel="noreferrer">Open pull request</a>
            )}
          </section>
        );
      })}
    </div>
  );
}

function SafeDiff({ selected, dark }: { selected: RepoFile; dark: boolean }) {
  const editorRef = useRef<Parameters<DiffOnMount>[0] | null>(null);
  useEffect(() => {
    return () => {
      const editor = editorRef.current;
      if (!editor) return;
      const model = editor.getModel();
      editor.setModel(null);
      model?.original.dispose();
      model?.modified.dispose();
    };
  }, []);
  return (
    <DiffEditor
      key={dark ? "dark" : "light"}
      height="280px"
      original={selected.original}
      modified={selected.modified}
      language={selected.path.endsWith(".py") ? "python" : "markdown"}
      keepCurrentOriginalModel
      keepCurrentModifiedModel
      theme={dark ? "vs-dark" : "light"}
      onMount={(editor) => {
        editorRef.current = editor;
      }}
      options={{
        readOnly: true,
        renderSideBySide: false,
        minimap: { enabled: false },
        wordWrap: "on",
        fontSize: 13,
        scrollBeyondLastLine: false,
      }}
    />
  );
}

function act(work: () => Promise<unknown>, ok: string) {
  void work().then(() => toast.success(ok)).catch((err: unknown) => toast.error(err instanceof Error ? err.message : "Request failed"));
}

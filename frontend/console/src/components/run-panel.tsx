import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { compactGoal, eventLabel, formatWhen, isFixturePublish, money, pullHref, statusTone } from "@/lib/format";
import type { RunView } from "@/lib/types";
import { GitPullRequest, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

const TERMINAL = new Set(["completed", "failed", "killed", "parked", "awaiting_approval"]);

export function RunPanel({ id, showTitle = false }: { id: string; showTitle?: boolean }) {
  const [view, setView] = useState<RunView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shown, setShown] = useState(1);

  useEffect(() => {
    let stop = false;
    async function poll() {
      try {
        const next = await api.view(id);
        if (stop) return;
        setView(next);
        setError(null);
        if (!TERMINAL.has(next.request.status)) {
          window.setTimeout(poll, 500);
        }
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
    if (!view || shown >= view.events.length) return;
    const timer = window.setTimeout(() => setShown((count) => count + 1), 120);
    return () => window.clearTimeout(timer);
  }, [shown, view]);

  if (error) {
    return <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>;
  }
  if (!view) {
    return (
      <div className="flex items-center gap-2 text-sm text-zinc-500">
        <Loader2 className="h-4 w-4 animate-spin" />
        Starting the run
      </div>
    );
  }

  const agent = view.agent;
  const events = view.events.slice(0, shown);
  const busy = !TERMINAL.has(view.request.status);

  return (
    <div className="space-y-3">
      {showTitle ? <h1 className="text-xl font-semibold">{view.request.title}</h1> : null}
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={statusTone(view.request.status)}>{view.request.status.replaceAll("_", " ")}</Badge>
        <span className="text-xs text-zinc-500">Risk {view.risk} · {view.risk_score}</span>
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-400" /> : null}
      </div>

      {view.questions.length > 0 && view.request.status === "parked" ? (
        <section className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950">
          <p className="text-sm font-medium">Need a decision</p>
          {view.questions.map((question) => (
            <div key={question.text} className="mt-2">
              <p className="text-sm">{question.text}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {(question.options ?? [question.default ?? "Proceed"]).map((option) => (
                  <Button key={option} size="sm" variant="secondary" onClick={() => answer(id, option)}>
                    {option}
                  </Button>
                ))}
              </div>
            </div>
          ))}
        </section>
      ) : null}

      {view.request.status === "awaiting_approval" ? (
        <div className="flex gap-2">
          <Button size="sm" onClick={() => decide(id, "approve")}>Approve plan</Button>
          <Button size="sm" variant="secondary" onClick={() => decide(id, "reject")}>Reject</Button>
        </div>
      ) : null}

      <section className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Plan</p>
        <ol className="mt-2 space-y-2">
          {planSteps(view).map((step, index) => (
            <li key={step.id ?? index} className="text-sm">
              <span className="font-medium">{step.id ?? `Step ${index + 1}`}</span>
              <span className="text-zinc-600 dark:text-zinc-400"> · {compactGoal(step.goal ?? "")}</span>
            </li>
          ))}
        </ol>
        {view.assumptions.length > 0 ? (
          <p className="mt-2 text-xs text-zinc-500">Assumptions: {view.assumptions.join("; ")}</p>
        ) : null}
      </section>

      <section className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
        <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Agent</p>
        <div className="mt-2 grid gap-1 text-sm sm:grid-cols-2">
          <p>Worker <span className="font-medium">{agent ? `${agent.id}@${agent.version}` : "Assembling"}</span></p>
          <p>Status <span className="font-medium">{agent?.status ?? "pending"}</span></p>
          <p>Harness <span className="font-medium">fixture</span></p>
          <p>Model <span className="font-medium">fixture</span></p>
          <p>Cost <span className="font-medium">{money(view.request.status === "completed" ? 0.01 : 0)}</span></p>
        </div>
      </section>

      <section className="rounded-lg border border-zinc-200 dark:border-zinc-800">
        <p className="border-b border-zinc-200 px-3 py-2 text-xs font-medium uppercase tracking-wide text-zinc-500 dark:border-zinc-800">
          Log
        </p>
        <ol className="max-h-48 overflow-auto px-3 py-2 font-mono text-[12px] leading-5 text-zinc-700 dark:text-zinc-300">
          {events.map((event) => (
            <li key={event.id}>
              <span className="text-zinc-400">{formatWhen(event.created_at)}</span> {eventLabel(event.type)}
            </li>
          ))}
        </ol>
      </section>

      {view.gates.length > 0 ? (
        <section className="space-y-2">
          {view.gates.map((gate) => (
            <div key={gate.gate} className="flex items-start justify-between gap-3 rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800">
              <div>
                <p className="font-medium">{gate.gate}</p>
                <p className="text-xs text-zinc-500">{(gate.findings ?? []).join(" · ") || "No findings"}</p>
              </div>
              <Badge tone={gate.verdict === "fail" ? "bad" : "ok"}>{gate.verdict}</Badge>
            </div>
          ))}
        </section>
      ) : null}

      {view.diff ? (
        <pre className="max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded-lg border border-zinc-800 bg-zinc-950 p-3 text-[12px] leading-5 text-zinc-100">
          {view.diff}
          {view.diff_kind === "fixture" ? "\n\n# Fixture preview. A keyed sandbox replaces this with the git diff." : ""}
        </pre>
      ) : null}

      {view.prs.map((pull) => {
        const href = pullHref(pull.url, id);
        const local = isFixturePublish(pull.url);
        return (
          <section key={pull.url} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
            <div className="flex items-center gap-2">
              <GitPullRequest className="h-4 w-4 text-emerald-600" />
              <p className="text-sm font-medium">Pull request #{pull.number}</p>
              <Badge tone="ok">open</Badge>
            </div>
            <p className="mt-1 text-xs text-zinc-500">
              {pull.head ?? "branch"} → {pull.base ?? "main"} · {pull.repo}
            </p>
            <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
              A person merges this pull request. The factory does not.
            </p>
            {local ? (
              <Link to={href} className="mt-3 inline-flex text-sm font-medium underline">
                Review in this run
              </Link>
            ) : (
              <a href={href} className="mt-3 inline-flex text-sm font-medium underline" target="_blank" rel="noreferrer">
                Open pull request
              </a>
            )}
          </section>
        );
      })}
    </div>
  );
}

function planSteps(view: RunView): { id?: string; goal?: string }[] {
  const plan = view.messages.find((message) => message.kind === "plan");
  const steps = plan?.payload.steps;
  if (Array.isArray(steps) && steps.length > 0) return steps as { id?: string; goal?: string }[];
  return [{ id: "step-1", goal: view.request.body }];
}

async function answer(id: string, text: string) {
  try {
    await api.answer(id, text);
    toast.success("Answer sent");
  } catch (err) {
    toast.error(err instanceof Error ? err.message : "Could not send the answer");
  }
}

async function decide(id: string, decision: "approve" | "reject") {
  try {
    await api.decide(id, decision);
    toast.success(decision === "approve" ? "Plan approved" : "Plan rejected");
  } catch (err) {
    toast.error(err instanceof Error ? err.message : "Could not record the decision");
  }
}

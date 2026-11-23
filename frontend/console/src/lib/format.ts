const LABELS: Record<string, string> = {
  "request.created": "Request accepted",
  "workflow.started": "Run started",
  "workflow.completed": "Run finished",
  "workflow.start_failed": "Run failed to start",
  "clarifier.asked": "Asked a clarifying question",
  "plan.ready": "Plan ready",
  "plan.decided": "Plan decision recorded",
  "agent.selected": "Agent assembled",
  "step.finished": "Step finished",
  "gates.finished": "Quality gates finished",
  "pr.opened": "Pull request opened",
  "run.killed": "Run stopped by the kill switch",
};

export function eventLabel(type: string): string {
  return LABELS[type] ?? type.replaceAll(".", " ");
}

export function statusTone(status: string): "neutral" | "run" | "wait" | "ok" | "bad" {
  if (status === "completed") return "ok";
  if (status === "failed" || status === "killed") return "bad";
  if (status === "parked" || status === "awaiting_approval") return "wait";
  if (status === "running" || status === "created") return "run";
  return "neutral";
}

export function formatWhen(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function money(usd: number): string {
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" }).format(usd);
}

export function pullHref(url: string, runId: string): string {
  try {
    const host = new URL(url).host;
    if (host === "example.test") return `/runs/${runId}`;
  } catch {
    return `/runs/${runId}`;
  }
  return url;
}

export function isFixturePublish(url: string): boolean {
  return pullHref(url, "x").startsWith("/runs/");
}

export function compactGoal(goal: string): string {
  const parts = goal
    .split(/\n+/)
    .map((part) => part.trim())
    .filter(Boolean);
  const unique = parts.filter((part, index) => parts.indexOf(part) === index);
  return unique[0] ?? goal;
}

export function repoLabel(target: string | null): string {
  if (!target) return "No repository";
  if (target.endsWith("examples/sample-repo") || target.endsWith("sample-repo")) return "local/sample";
  if (target.startsWith("/")) return target.split("/").filter(Boolean).at(-1) ?? target;
  return target;
}

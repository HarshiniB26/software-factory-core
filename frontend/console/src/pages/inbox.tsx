import { api } from "@/lib/api";
import type { InboxItem } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

export function InboxPage() {
  const [items, setItems] = useState<InboxItem[] | null>(null);
  async function load() {
    const payload = await api.inbox();
    setItems(payload.items);
  }
  useEffect(() => {
    load().catch((err: unknown) => toast.error(err instanceof Error ? err.message : "Could not load the inbox"));
  }, []);
  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <h1 className="wordmark text-2xl font-semibold tracking-tight">Inbox</h1>
      <p className="mt-1 text-sm text-zinc-500">Questions and plan approvals. Everything else keeps moving.</p>
      {items === null ? <div className="mt-6 h-32 animate-pulse rounded-2xl bg-white/50" /> : null}
      {items && items.length === 0 ? (
        <p className="surface mt-6 rounded-2xl px-4 py-10 text-sm text-zinc-500">Nothing needs you.</p>
      ) : null}
      <ul className="mt-6 space-y-3">
        {(items ?? []).map((item) => (
          <li key={item.id} className="surface rounded-2xl p-4">
            <p className="text-xs uppercase tracking-wide text-[var(--accent-2)]">{item.kind === "approval" ? "Approval" : "Question"}</p>
            <p className="mt-1 text-base font-medium">{item.question || item.title}</p>
            <p className="mt-1 text-sm text-zinc-500">{item.title}</p>
            <div className="mt-3 flex gap-2">
              {item.status === "parked" ? (
                <Button size="sm" onClick={() => api.answer(item.id, "Use the smallest change").then(load).then(() => toast.success("Answer sent"))}>
                  Use the smallest change
                </Button>
              ) : null}
              {item.status === "awaiting_approval" ? (
                <>
                  <Button size="sm" onClick={() => api.decide(item.id, "approve").then(load).then(() => toast.success("Plan approved"))}>Approve</Button>
                  <Button size="sm" variant="secondary" onClick={() => api.decide(item.id, "reject").then(load).then(() => toast.success("Plan rejected"))}>Reject</Button>
                </>
              ) : null}
              <Link to={`/runs/${item.id}`} className="self-center text-sm underline">Open run</Link>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

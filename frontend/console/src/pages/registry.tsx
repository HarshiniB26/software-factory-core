import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { money, statusTone } from "@/lib/format";
import type { AgentCard } from "@/lib/types";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

export function RegistryPage() {
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState<AgentCard[]>([]);
  const [skills, setSkills] = useState<{ id: string; version: string; license: string }[]>([]);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  useEffect(() => {
    Promise.all([api.catalog(), api.skills()]).then(([agents, skillList]) => {
      setCatalog(agents.catalog ?? []);
      setSkills(skillList.skills);
    }).catch((err: unknown) => toast.error(err instanceof Error ? err.message : "Could not load the registry"));
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Registry</h1>
          <p className="mt-1 text-sm text-zinc-500">Versions, held-out scores, and why a promotion was kept or shipped.</p>
        </div>
        <Button onClick={() => setOpen(true)}>New app</Button>
      </div>
      <div className="mt-6 grid gap-3">
        {catalog.map((agent) => (
          <article key={`${agent.id}@${agent.version}`} className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-medium">{agent.id}@{agent.version}</p>
              <Badge tone={statusTone(agent.status)}>{agent.status}</Badge>
            </div>
            <p className="mt-2 text-xs text-zinc-500">
              Held-out {Math.round((agent.pass_rate ?? 0) * 100)}% of {agent.n} · {money(agent.cost_per_task_usd ?? 0)} / task
              {agent.parent ? ` · parent ${agent.parent}` : ""}
            </p>
            <ul className="mt-3 space-y-1 text-xs text-zinc-600 dark:text-zinc-400">
              {(agent.promotions ?? []).map((item) => (
                <li key={item.version + item.result}>{item.version}: {item.result}. {item.reason}</li>
              ))}
            </ul>
            <Button
              className="mt-3"
              size="sm"
              variant="secondary"
              onClick={async () => {
                const result = await api.promote(agent.id, agent.version);
                toast.success(result.allowed ? result.reason : `Held: ${result.reason}`);
              }}
            >
              Ask the promotion gate
            </Button>
          </article>
        ))}
      </div>
      <h2 className="mt-8 text-sm font-medium">Pinned skills</h2>
      <ul className="mt-2 grid gap-2 sm:grid-cols-2">
        {skills.map((skill) => (
          <li key={skill.id} className="rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800">
            {skill.id} <span className="text-zinc-500">· {skill.license} · {skill.version}</span>
          </li>
        ))}
      </ul>
      {open ? (
        <form
          className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4"
          onSubmit={async (event) => {
            event.preventDefault();
            const created = await api.newApp(name, description);
            navigate(`/runs/${created.id}`);
          }}
        >
          <div className="w-full max-w-md rounded-xl bg-white p-5 dark:bg-zinc-950" onClick={(event) => event.stopPropagation()}>
            <h2 className="text-base font-semibold">New app</h2>
            <input required value={name} onChange={(event) => setName(event.target.value)} placeholder="Name" className="mt-3 h-9 w-full rounded-md border border-zinc-200 bg-transparent px-2 dark:border-zinc-800" />
            <textarea required value={description} onChange={(event) => setDescription(event.target.value)} placeholder="What it should do" className="mt-2 min-h-24 w-full rounded-md border border-zinc-200 bg-transparent px-2 py-2 dark:border-zinc-800" />
            <div className="mt-3 flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
              <Button type="submit">Create</Button>
            </div>
          </div>
        </form>
      ) : null}
    </div>
  );
}

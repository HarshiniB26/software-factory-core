import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { statusTone } from "@/lib/format";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

export function RegistryPage() {
  const navigate = useNavigate();
  const [agents, setAgents] = useState<{ id: string; version: string; status: string; capabilities: string[] }[]>([]);
  const [skills, setSkills] = useState<{ id: string; version: string; license: string }[]>([]);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    Promise.all([api.agents(), api.skills()])
      .then(([agentList, skillList]) => {
        setAgents(agentList.agents);
        setSkills(skillList.skills);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load the registry"));
  }, []);

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Registry</h1>
          <p className="mt-1 text-sm text-zinc-500">Agents are assembled per run. Skills are pinned and license-checked.</p>
        </div>
        <Button onClick={() => setOpen(true)}>New app</Button>
      </div>
      {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}
      <div className="mt-8 grid gap-8 md:grid-cols-2">
        <section>
          <h2 className="text-sm font-medium">Agents</h2>
          {agents.length === 0 ? <p className="mt-3 text-sm text-zinc-500">No agents have been registered.</p> : null}
          <ul className="mt-3 space-y-2">
            {agents.map((agent) => (
              <li key={`${agent.id}@${agent.version}`} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium">{agent.id}@{agent.version}</p>
                  <Badge tone={statusTone(agent.status)}>{agent.status}</Badge>
                </div>
                <p className="mt-1 text-xs text-zinc-500">{agent.capabilities.join(", ") || "No capabilities listed"}</p>
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h2 className="text-sm font-medium">Skills</h2>
          {skills.length === 0 ? <p className="mt-3 text-sm text-zinc-500">No skills are registered yet.</p> : null}
          <ul className="mt-3 space-y-2">
            {skills.map((skill) => (
              <li key={`${skill.id}@${skill.version}`} className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800">
                <span className="font-medium">{skill.id}</span>
                <span className="text-zinc-500"> · {skill.license} · {skill.version}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
      {open ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
          <form
            className="w-full max-w-md rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950"
            onSubmit={async (event) => {
              event.preventDefault();
              try {
                const created = await api.newApp(name, description);
                toast.success("App request started");
                navigate(`/runs/${created.id}`);
              } catch (err) {
                toast.error(err instanceof Error ? err.message : "Could not start the app");
              }
            }}
          >
            <h2 className="text-base font-semibold">New app</h2>
            <label className="mt-4 block text-sm">
              Name
              <input
                required
                value={name}
                onChange={(event) => setName(event.target.value)}
                className="mt-1 h-9 w-full rounded-md border border-zinc-200 bg-transparent px-2 dark:border-zinc-800"
              />
            </label>
            <label className="mt-3 block text-sm">
              What it should do
              <textarea
                required
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                className="mt-1 min-h-24 w-full rounded-md border border-zinc-200 bg-transparent px-2 py-2 dark:border-zinc-800"
              />
            </label>
            <div className="mt-4 flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit">Create</Button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}

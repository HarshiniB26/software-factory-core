import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useSession } from "@/components/shell";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import { useTheme } from "@/lib/theme";
import type { WorkspaceSettings } from "@/lib/types";
import { useEffect, useState } from "react";
import { toast } from "sonner";

export function SettingsPage() {
  const session = useSession();
  const { theme, toggle } = useTheme();
  const [modules, setModules] = useState<{ id: string; version: string; implements: string }[]>([]);
  const [selected, setSelected] = useState<Record<string, string | string[]>>({});
  const [cost, setCost] = useState<{ pull_requests: number; estimated_usd: number } | null>(null);
  const [killed, setKilled] = useState(false);
  const [confirmKill, setConfirmKill] = useState(false);
  const [user, setUser] = useState("");
  const [workspace, setWorkspace] = useState<WorkspaceSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.modules(), api.cost(), api.audit(), api.settings()])
      .then(([moduleList, spend, audit, settings]) => {
        setModules(moduleList.installed);
        setSelected(moduleList.selected);
        setCost(spend);
        setKilled(audit.kill_switch);
        setWorkspace(settings);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load settings"));
  }, []);

  const chosen = new Set(Object.values(selected).flatMap((value) => (Array.isArray(value) ? value : [value])));
  const active = modules.filter((module) => chosen.has(module.id));
  const rest = modules.filter((module) => !chosen.has(module.id));

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setConfirmKill(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <h1 className="text-xl font-semibold">Settings</h1>
      <p className="mt-1 text-sm text-zinc-500">Workspace, spend, and the kill switch. Pull requests stay unmerged.</p>
      {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}

      <section className="mt-8">
        <h2 className="text-sm font-medium">Appearance</h2>
        <Button className="mt-3" variant="secondary" onClick={toggle}>
          Use {theme === "dark" ? "light" : "dark"} theme
        </Button>
      </section>

      <section className="mt-8">
        <h2 className="text-sm font-medium">Roles</h2>
        <p className="mt-1 text-sm text-zinc-500">Harness and model shown on each agent card. Dev mode still runs locally, without a live key.</p>
        {workspace ? (
          <form
            className="mt-3 space-y-3"
            onSubmit={async (event) => {
              event.preventDefault();
              const saved = await api.saveSettings(workspace);
              setWorkspace(saved);
              toast.success("Settings saved");
            }}
          >
            <label className="block text-sm">
              Plan approval
              <select
                value={workspace.plan_approval}
                onChange={(event) => setWorkspace({ ...workspace, plan_approval: event.target.value })}
                className="mt-1 h-9 w-full rounded-md border border-zinc-200 bg-transparent px-2 dark:border-zinc-800"
              >
                <option value="high_risk">High risk only</option>
                <option value="always">Always</option>
                <option value="never">Never</option>
              </select>
            </label>
            {Object.entries(workspace.roles).map(([role, choice]) => (
              <div key={role} className="grid gap-2 sm:grid-cols-3">
                <p className="self-center text-sm capitalize">{role}</p>
                <input
                  value={choice.harness}
                  onChange={(event) =>
                    setWorkspace({
                      ...workspace,
                      roles: { ...workspace.roles, [role]: { ...choice, harness: event.target.value } },
                    })
                  }
                  className="h-9 rounded-md border border-zinc-200 bg-transparent px-2 text-sm dark:border-zinc-800"
                />
                <input
                  value={choice.model}
                  onChange={(event) =>
                    setWorkspace({
                      ...workspace,
                      roles: { ...workspace.roles, [role]: { ...choice, model: event.target.value } },
                    })
                  }
                  className="h-9 rounded-md border border-zinc-200 bg-transparent px-2 text-sm dark:border-zinc-800"
                />
              </div>
            ))}
            <Button type="submit">Save settings</Button>
          </form>
        ) : (
          <div className="mt-3 h-24 animate-pulse rounded-xl bg-zinc-200 dark:bg-zinc-800" />
        )}
      </section>

      <section id="github" className="mt-8 scroll-mt-8">
        <h2 className="text-sm font-medium">GitHub</h2>
        <p className="mt-1 text-sm text-zinc-500">
          Sign-in uses <span className="font-mono text-xs">FACTORY_GITHUB_CLIENT_ID</span> and{" "}
          <span className="font-mono text-xs">FACTORY_GITHUB_CLIENT_SECRET</span>. Without them, Connect GitHub stays in the composer and explains that the local sample is still available.
        </p>
        {session.oauth ? (
          <a className="mt-3 inline-flex text-sm font-medium underline" href="/api/auth/github/login">
            Connect GitHub
          </a>
        ) : (
          <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">The OAuth app is not configured in this workspace.</p>
        )}
      </section>

      <section className="mt-8">
        <h2 className="text-sm font-medium">Session</h2>
        <p className="mt-1 text-sm text-zinc-500">
          Signed in as {session.principal?.id ?? "nobody"} ({session.principal?.roles.join(", ")}). Mode {session.mode}.
        </p>
        {session.mode === "fixture" ? (
          <form
            className="mt-3 flex gap-2"
            onSubmit={async (event) => {
              event.preventDefault();
              try {
                await api.login(user, "approver");
                await session.refresh();
                toast.success(`Signed in as ${user}`);
              } catch (err) {
                toast.error(err instanceof Error ? err.message : "Sign-in failed");
              }
            }}
          >
            <input
              required
              value={user}
              placeholder="Name"
              onChange={(event) => setUser(event.target.value)}
              className="h-9 rounded-md border border-zinc-200 bg-transparent px-2 text-sm dark:border-zinc-800"
            />
            <Button type="submit" variant="secondary">
              Dev sign-in
            </Button>
          </form>
        ) : (
          <a className="mt-3 inline-flex text-sm font-medium underline" href="/api/auth/github/login">
            Sign in with GitHub
          </a>
        )}
      </section>

      <section className="mt-8">
        <h2 className="text-sm font-medium">Spend</h2>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          {cost ? `${cost.pull_requests} pull requests · ${money(cost.estimated_usd)} fixture estimate` : "Loading spend"}
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-sm font-medium">Modules</h2>
        <h3 className="mt-3 text-xs font-medium uppercase tracking-wide text-zinc-400">In this workspace</h3>
        <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
          {active.map((module) => (
            <li key={module.id} className="flex items-center justify-between py-2 text-sm">
              <span>
                {module.id}
                <span className="text-zinc-500"> · {module.implements}</span>
              </span>
              <Badge tone="ok">selected</Badge>
            </li>
          ))}
        </ul>
        <h3 className="mt-6 text-xs font-medium uppercase tracking-wide text-zinc-400">Available</h3>
        <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
          {rest.map((module) => (
            <li key={module.id} className="flex items-center justify-between py-2 text-sm">
              <span>
                {module.id}
                <span className="text-zinc-500"> · {module.implements}</span>
              </span>
              <span className="text-xs text-zinc-400">{module.version}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-8 rounded-lg border border-red-200 p-4 dark:border-red-900">
        <h2 className="text-sm font-medium">Kill switch</h2>
        <p className="mt-1 text-sm text-zinc-500">
          {killed ? "New work is stopped." : "Runs are allowed. This does not merge or close pull requests."}
        </p>
        <div className="mt-3 flex gap-2">
          <Button variant="danger" onClick={() => setConfirmKill(true)} disabled={killed}>
            Stop runs
          </Button>
          <Button
            variant="secondary"
            disabled={!killed}
            onClick={async () => {
              await api.resume();
              setKilled(false);
              toast.success("Runs resumed");
            }}
          >
            Resume
          </Button>
        </div>
      </section>
      {confirmKill ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-5 dark:bg-zinc-950">
            <h2 className="text-base font-semibold">Stop every new run?</h2>
            <p className="mt-2 text-sm text-zinc-500">In-flight work is marked killed. Open pull requests stay open.</p>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setConfirmKill(false)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={async () => {
                  await api.kill();
                  setKilled(true);
                  setConfirmKill(false);
                  toast.success("Kill switch is on");
                }}
              >
                Stop runs
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

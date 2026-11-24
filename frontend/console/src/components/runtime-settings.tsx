import { useEffect, useState } from "react";
import { useSession } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { RuntimeInfo } from "@/lib/types";

export function RuntimeSettings() {
  const session = useSession();
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [approval, setApproval] = useState("high_risk");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  useEffect(() => { let active = true; api.runtime().then((value) => { if (active) { setRuntime(value); setProvider(value.provider ?? ""); setModel(value.model ?? ""); setApproval(value.approval); } }).catch((err: unknown) => { if (active) setError(err instanceof Error ? err.message : "Runtime unavailable"); }); return () => { active = false; }; }, []);
  const models = runtime?.providers.find((item) => item.id === provider)?.models ?? [];
  const allowed = session.principal?.roles.includes("admin");
  return <section className="mt-8 rounded-xl border border-[var(--line)] p-5">
    <div className="flex items-center justify-between"><h2 className="text-sm font-semibold">Execution runtime</h2><span className="text-xs">{runtime ? runtime.execution_mode === "demo" ? "Demo · simulated" : runtime.ready ? "Configured" : "Setup required" : "Checking configuration"}</span></div>
    <p className="mt-2 text-sm text-zinc-500">One coding session carries repository context through discovery, implementation, verification, and reflection.</p>
    {error && <p role="alert" className="mt-3 text-sm text-red-600">{error}</p>}
    {runtime && <form className="mt-4 space-y-3" onSubmit={async (event) => { event.preventDefault(); setSaving(true); setSaved(false); setError(null); try { setRuntime(await api.saveRuntime(provider, model, approval)); setSaved(true); } catch (err) { setError(err instanceof Error ? err.message : "Could not save runtime"); } finally { setSaving(false); } }}>
      <label className="block text-sm">Provider<select aria-label="Execution provider" className="mt-1 block h-10 w-full rounded-md border border-[var(--line)] bg-[var(--card)] px-3" value={provider} disabled={!allowed} onChange={(event) => { setProvider(event.target.value); setModel(""); setSaved(false); }}><option value="">Select a configured provider</option>{runtime.providers.map((item) => <option key={item.id} value={item.id} disabled={!item.enabled || !item.models.length}>{item.name}{!item.enabled ? " · disabled" : !item.models.length ? " · no models" : ""}</option>)}</select></label>
      <label className="block text-sm">Model<select aria-label="Execution model" className="mt-1 block h-10 w-full rounded-md border border-[var(--line)] bg-[var(--card)] px-3" value={model} disabled={!allowed || !models.length} onChange={(event) => { setModel(event.target.value); setSaved(false); }}><option value="">Select a model</option>{models.map((name) => <option key={name}>{name}</option>)}</select></label>
      <label className="block text-sm">Approval policy<select aria-label="Approval policy" className="mt-1 block h-10 w-full rounded-md border border-[var(--line)] bg-[var(--card)] px-3" value={approval} disabled={!allowed} onChange={(event) => setApproval(event.target.value)}><option value="high_risk">Pause for high-risk changes only</option><option value="always">Review every plan</option></select></label>
      {allowed ? <Button type="submit" disabled={saving || !provider || !models.includes(model)}>{saving ? "Saving…" : "Save runtime"}</Button> : <p className="text-xs text-zinc-500">An administrator can change the execution runtime.</p>}
      {saved && <p role="status" className="text-sm">Saved. New requests will use this selection.</p>}
      <p className="text-xs leading-5 text-zinc-500">Routine requests proceed automatically; high-risk changes require approval. Execution uses the trusted worker host. Provider billing is unavailable; an unknown cost is not a zero cost.</p>
    </form>}
  </section>;
}

import { Badge } from "@/components/ui/badge";
import { useSession } from "@/components/shell";
import { formatWhen, money, repoLabel, statusTone } from "@/lib/format";
import { api } from "@/lib/api";
import type { CostReport } from "@/lib/types";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const FILTERS = ["all", "completed", "running", "parked", "failed"] as const;

export function RunsPage() {
  const { runs } = useSession();
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
  const [query, setQuery] = useState("");
  const [report, setReport] = useState<CostReport | null>(null);
  useEffect(() => {
    api.cost().then(setReport).catch(() => setReport(null));
  }, []);
  const visible = useMemo(
    () =>
      runs.filter((run) => {
        const statusOk = filter === "all" || run.status === filter || (filter === "running" && run.status === "created");
        return statusOk && run.title.toLowerCase().includes(query.toLowerCase());
      }),
    [runs, filter, query],
  );

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <h1 className="wordmark text-2xl font-semibold tracking-tight">Runs</h1>
      <p className="mt-1 text-sm text-zinc-500">Status, spend, success, and how long a run takes.</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <Stat label="Open and finished" value={String(runs.length)} />
        <Stat label="Success rate" value={report ? `${Math.round(report.success_rate * 100)}%` : "—"} />
        <Stat label="Provider spend" value={report ? money(report.estimated_usd) : "Unavailable"} />
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <Chart title="Runs over time">
          {report ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={report.series}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(127,127,127,0.2)" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="completed" stackId="s" fill="#0c6e62" name="Completed" />
                <Bar dataKey="failed" stackId="s" fill="#d4534a" name="Failed" />
                <Bar dataKey="running" stackId="s" fill="#d9773a" name="Running" />
                <Bar dataKey="parked" stackId="s" fill="#c4a15a" name="Parked" />
              </BarChart>
            </ResponsiveContainer>
          ) : <Skeleton />}
        </Chart>
        <Chart title="Cost per day">
          {report ? (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={report.series}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(127,127,127,0.2)" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(value) => money(Number(value))} />
                <Area dataKey="usd" stroke="#0c6e62" fill="#0c6e62" fillOpacity={0.25} name="USD" />
              </AreaChart>
            </ResponsiveContainer>
          ) : <Skeleton />}
        </Chart>
        <Chart title="Success rate">
          {report ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={report.series}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(127,127,127,0.2)" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} domain={[0, 1]} />
                <Tooltip formatter={(value) => `${Math.round(Number(value) * 100)}%`} />
                <Line dataKey="success_rate" stroke="#1c7a4a" strokeWidth={2} dot={false} name="Success" />
              </LineChart>
            </ResponsiveContainer>
          ) : <Skeleton />}
        </Chart>
        <Chart title="Average duration">
          {report ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={report.series}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(127,127,127,0.2)" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(value) => `${Math.round(Number(value))}s`} />
                <Line dataKey="average_duration_seconds" stroke="#d9773a" strokeWidth={2} dot={false} name="Seconds" />
              </LineChart>
            </ResponsiveContainer>
          ) : <Skeleton />}
        </Chart>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {FILTERS.map((item) => (
          <button key={item} className={`rounded-full px-3 py-1 text-xs ${filter === item ? "bg-[var(--accent)] text-white" : "bg-white/80 dark:bg-white/10"}`} onClick={() => setFilter(item)}>
            {item}
          </button>
        ))}
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter by title" className="h-8 rounded-full border border-zinc-200 bg-transparent px-3 text-sm dark:border-zinc-800" />
      </div>
      {visible.length === 0 ? (
        <p className="mt-8 rounded-xl border border-dashed border-zinc-300 px-4 py-10 text-sm text-zinc-500">No runs match this filter.</p>
      ) : (
        <ul className="mt-4 divide-y divide-zinc-200 dark:divide-zinc-800">
          {visible.map((run) => (
            <li key={run.id}>
              <Link to={`/runs/${run.id}`} className="flex items-center justify-between gap-4 py-3">
                <span>
                  <span className="block text-sm font-medium">{run.title}</span>
                  <span className="text-xs text-zinc-500">{formatWhen(run.created_at)} · {repoLabel(run.target)}</span>
                </span>
                <Badge tone={statusTone(run.status)}>{run.status.replaceAll("_", " ")}</Badge>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <article className="surface rounded-2xl p-4">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="wordmark mt-1 text-2xl font-semibold">{value}</p>
    </article>
  );
}

function Chart({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="surface rounded-2xl p-4">
      <h2 className="mb-2 text-sm font-medium">{title}</h2>
      {children}
    </section>
  );
}

function Skeleton() {
  return <div className="h-[200px] animate-pulse rounded-xl bg-white/40 dark:bg-white/5" />;
}

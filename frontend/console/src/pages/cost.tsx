import { api } from "@/lib/api";
import { money } from "@/lib/format";
import type { CostReport } from "@/lib/types";
import { useEffect, useState, type ReactNode } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function CostPage() {
  const [report, setReport] = useState<CostReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.cost().then(setReport).catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load usage"));
  }, []);
  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <h1 className="wordmark text-2xl font-semibold tracking-tight">Usage</h1>
      <p className="mt-1 text-sm text-zinc-500">Spend, outcomes, and how long a run takes. Fixture prices until a live key is set.</p>
      {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}
      {!report ? <div className="mt-6 h-48 animate-pulse rounded-2xl bg-white/50" /> : null}
      {report ? (
        <>
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <Tile label="Spend" value={money(report.estimated_usd)} />
            <Tile label="Success rate" value={`${Math.round(report.success_rate * 100)}%`} />
            <Tile label="Average duration" value={`${Math.round(report.average_duration_seconds)}s`} />
          </div>
          <Chart title="Runs by status">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={report.series}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(127,127,127,0.25)" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="completed" stackId="s" fill="#0c6e62" name="Completed" />
                <Bar dataKey="failed" stackId="s" fill="#d4534a" name="Failed" />
                <Bar dataKey="running" stackId="s" fill="#d9773a" name="Running" />
                <Bar dataKey="parked" stackId="s" fill="#c4a15a" name="Parked" />
                <Legend />
              </BarChart>
            </ResponsiveContainer>
          </Chart>
          <Chart title="Cost per day">
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={report.series}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(127,127,127,0.25)" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(value) => money(Number(value))} />
                <Area dataKey="usd" stroke="#0c6e62" fill="#0c6e62" fillOpacity={0.25} name="USD" />
              </AreaChart>
            </ResponsiveContainer>
          </Chart>
          <div className="grid gap-3 lg:grid-cols-2">
            <Chart title="Success rate">
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={report.series}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(127,127,127,0.25)" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(value) => `${Math.round(Number(value) * 100)}%`} />
                  <Legend />
                  <Line dataKey="success_rate" stroke="#1c7a4a" strokeWidth={2} dot={false} name="Success" />
                </LineChart>
              </ResponsiveContainer>
            </Chart>
            <Chart title="Average duration">
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={report.series}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(127,127,127,0.25)" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(value) => `${Math.round(Number(value))}s`} />
                  <Line dataKey="average_duration_seconds" stroke="#d9773a" strokeWidth={2} dot={false} name="Seconds" />
                </LineChart>
              </ResponsiveContainer>
            </Chart>
          </div>
        </>
      ) : null}
    </div>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <article className="surface rounded-2xl p-4">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="wordmark mt-1 text-2xl font-semibold">{value}</p>
    </article>
  );
}

function Chart({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="surface mt-4 rounded-2xl p-4">
      <h2 className="mb-2 text-sm font-medium">{title}</h2>
      {children}
    </section>
  );
}

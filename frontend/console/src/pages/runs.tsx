import { Badge } from "@/components/ui/badge";
import { useSession } from "@/components/shell";
import { formatWhen, repoLabel, statusTone } from "@/lib/format";
import { Link } from "react-router-dom";

export function RunsPage() {
  const { runs } = useSession();
  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <h1 className="text-xl font-semibold">Runs</h1>
      <p className="mt-1 text-sm text-zinc-500">Every request, including ones waiting on you.</p>
      {runs.length === 0 ? (
        <p className="mt-8 rounded-lg border border-dashed border-zinc-300 px-4 py-8 text-sm text-zinc-500 dark:border-zinc-700">
          No runs yet. Describe an issue to start one.
        </p>
      ) : (
        <ul className="mt-6 divide-y divide-zinc-200 dark:divide-zinc-800">
          {runs.map((run) => (
            <li key={run.id}>
              <Link to={`/runs/${run.id}`} className="flex items-center justify-between gap-4 py-3 hover:bg-zinc-100/60 dark:hover:bg-zinc-900">
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

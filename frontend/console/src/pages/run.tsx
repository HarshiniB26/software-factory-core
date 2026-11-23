import { RunPanel } from "@/components/run-panel";
import { Link, useParams } from "react-router-dom";

export function RunPage() {
  const { id } = useParams();
  if (!id) return null;
  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <Link to="/runs" className="text-sm text-zinc-500 hover:underline">
        Runs
      </Link>
      <div className="mt-4">
        <RunPanel id={id} showTitle />
      </div>
    </div>
  );
}

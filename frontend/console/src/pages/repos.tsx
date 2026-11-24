import { useSession } from "@/components/shell";
import { Button } from "@/components/ui/button";

export function ReposPage() {
  const { repos, connected, mode, connect, oauth } = useSession();
  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <h1 className="text-xl font-semibold tracking-tight">Repositories</h1>
      <p className="mt-1 text-sm text-zinc-500">
        {mode === "github-app"
          ? "The GitHub App is configured. Connect a repo the factory may open pull requests against."
          : "Dev mode. Connect the bundled sample, or sign in with GitHub once an OAuth app exists."}
      </p>
      <div className="mt-6 space-y-3">
        {repos.map((repo) => (
          <article key={repo.full_name} className="flex items-center justify-between gap-4 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
            <div>
              <p className="text-sm font-medium">{repo.full_name}</p>
              <p className="mt-1 text-xs text-zinc-500">{repo.description}</p>
            </div>
            <Button
              size="sm"
              variant={connected?.full_name === repo.full_name ? "secondary" : "default"}
              onClick={() => void connect(repo.full_name)}
            >
              {connected?.full_name === repo.full_name ? "Connected" : "Connect"}
            </Button>
          </article>
        ))}
      </div>
      {oauth ? (
        <a className="mt-6 inline-flex text-sm font-medium underline" href="/api/auth/github/login">
          Connect GitHub
        </a>
      ) : (
        <p className="mt-6 text-sm text-zinc-500">
          GitHub sign-in needs the OAuth app. See Settings → GitHub. The local sample stays available.
        </p>
      )}
    </div>
  );
}

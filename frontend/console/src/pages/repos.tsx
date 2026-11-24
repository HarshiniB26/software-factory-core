import { useSession } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { Github } from "lucide-react";

export function ReposPage() {
  const { repos, connected, mode, connect, disconnect, oauth, github, installUrl, disconnectGithub } = useSession();
  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <h1 className="text-xl font-semibold tracking-tight">Repositories</h1>
      <p className="mt-1 text-sm text-zinc-500">
        {mode === "github-app"
          ? "The GitHub App is configured. Connect a repo the factory may open pull requests against."
          : "Dev mode. Connect the bundled sample, or sign in with GitHub once an OAuth app exists."}
      </p>
      {github ? (
        <div className="mt-4 flex items-center gap-3 rounded-xl border border-[var(--line)] px-3 py-3">
          {github.avatar_url ? <img src={github.avatar_url} alt="" className="h-8 w-8 rounded-full" /> : <Github className="h-4 w-4" />}
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">{github.login}</p>
            <p className="text-xs text-zinc-500">{github.installed ? "App installed" : "App not installed on any repos"}</p>
          </div>
          {installUrl ? (
            <a href={installUrl} target="_blank" rel="noreferrer" className="text-sm font-medium underline">
              Add repositories
            </a>
          ) : null}
          <Button size="sm" variant="secondary" onClick={() => void disconnectGithub()}>
            Disconnect
          </Button>
        </div>
      ) : null}
      <div className="mt-6 space-y-3">
        {repos.map((repo) => {
          const current = connected?.full_name === repo.full_name;
          return (
            <article key={repo.full_name} className="flex items-center justify-between gap-4 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
              <div>
                <p className="text-sm font-medium">{repo.full_name}</p>
                <p className="mt-1 text-xs text-zinc-500">
                  {repo.kind === "github" && repo.private ? "Private · " : ""}
                  {repo.default_branch ? `${repo.default_branch} · ` : ""}
                  {repo.description}
                </p>
              </div>
              {current ? (
                <Button size="sm" variant="secondary" onClick={() => void disconnect(repo.full_name)}>
                  Disconnect
                </Button>
              ) : (
                <Button size="sm" onClick={() => void connect(repo.full_name)}>
                  Connect
                </Button>
              )}
            </article>
          );
        })}
      </div>
      {oauth && !github ? (
        <a className="mt-6 inline-flex text-sm font-medium underline" href="/api/auth/github/login">
          Connect GitHub
        </a>
      ) : null}
      {oauth ? null : (
        <p className="mt-6 text-sm text-zinc-500">
          GitHub sign-in needs the OAuth app. See Settings → GitHub. The local sample stays available.
        </p>
      )}
    </div>
  );
}

import type { Repo } from "@/lib/types";

export function groupRepos(repos: Repo[]): { local: Repo[]; github: Repo[] } {
  return {
    local: repos.filter((repo) => repo.kind !== "github"),
    github: repos.filter((repo) => repo.kind === "github"),
  };
}

export function filterRepos(repos: Repo[], query: string): Repo[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return repos;
  return repos.filter((repo) => {
    const haystack = `${repo.full_name} ${repo.description}`.toLowerCase();
    return haystack.includes(needle);
  });
}

export function issueTarget(repo: Pick<Repo, "path" | "full_name"> | null): string | null {
  if (!repo?.full_name) return null;
  return repo.path || repo.full_name;
}

export const GITHUB_OAUTH_NOTE = "GitHub sign-in needs the OAuth app.";

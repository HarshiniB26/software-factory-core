import { Button } from "@/components/ui/button";
import { api, captureSessionToken, sessionFromRedirect } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatWhen } from "@/lib/format";
import { useTheme } from "@/lib/theme";
import type { GitHubAccount, Principal, Repo, RequestRow } from "@/lib/types";
import {
  CircleDollarSign,
  FolderGit2,
  Inbox,
  Library,
  Menu,
  Moon,
  Plus,
  ScrollText,
  Settings,
  Sun,
  X,
} from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { toast } from "sonner";

type Session = {
  principal: Principal | null;
  repos: Repo[];
  connected: Repo | null;
  mode: string;
  oauth: boolean;
  github: GitHubAccount | null;
  installUrl: string | null;
  runs: RequestRow[];
  refresh: () => Promise<void>;
  connect: (fullName: string, branch?: string) => Promise<void>;
  disconnect: (fullName: string) => Promise<void>;
  refreshGithub: () => Promise<void>;
  disconnectGithub: () => Promise<void>;
};

const SessionContext = createContext<Session | null>(null);

export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error("Session missing");
  return value;
}

export function Shell() {
  const navigate = useNavigate();
  const { theme, toggle } = useTheme();
  const [principal, setPrincipal] = useState<Principal | null>(null);
  const [repos, setRepos] = useState<Repo[]>([]);
  const [connected, setConnected] = useState<Repo | null>(null);
  const [mode, setMode] = useState("fixture");
  const [oauth, setOauth] = useState(false);
  const [github, setGithub] = useState<GitHubAccount | null>(null);
  const [installUrl, setInstallUrl] = useState<string | null>(null);
  const [runs, setRuns] = useState<RequestRow[]>([]);
  const [menu, setMenu] = useState(false);
  const [palette, setPalette] = useState(false);
  const [connectOpen, setConnectOpen] = useState(false);

  const applyList = useCallback((repoList: Awaited<ReturnType<typeof api.repos>>) => {
    setRepos(repoList.repos);
    setConnected(repoList.connected?.full_name ? repoList.connected : null);
    setMode(repoList.mode);
    setOauth(Boolean(repoList.oauth));
    setGithub(repoList.github ?? null);
    setInstallUrl(repoList.install_url ?? null);
  }, []);

  const refresh = useCallback(async () => {
    const [me, repoList, requestList] = await Promise.all([api.me(), api.repos(), api.requests()]);
    setPrincipal(me);
    applyList(repoList);
    setRuns([...requestList].sort((left, right) => right.created_at.localeCompare(left.created_at)));
  }, [applyList]);

  const connect = useCallback(async (fullName: string, branch?: string) => {
    const repo = await api.connect(fullName, branch);
    setConnected(repo.full_name ? repo : null);
    setConnectOpen(false);
    toast.success(`Connected ${repo.full_name}`);
  }, []);

  const disconnect = useCallback(async (fullName: string) => {
    await api.disconnectRepo(fullName);
    setConnected(null);
    toast.success(`Disconnected ${fullName}`);
  }, []);

  const refreshGithub = useCallback(async () => {
    applyList(await api.refreshGithub());
    toast.success("GitHub repositories refreshed");
  }, [applyList]);

  const disconnectGithub = useCallback(async () => {
    await api.disconnectGithub();
    await refresh();
    toast.success("Disconnected GitHub");
  }, [refresh]);

  useEffect(() => {
    const returned = sessionFromRedirect(window.location.search).token !== null;
    captureSessionToken();
    const load = async () => {
      if (returned) {
        try {
          applyList(await api.refreshGithub());
        } catch {
          // The signed-in user may not have a GitHub account yet.
        }
      }
      await refresh();
    };
    load().catch((err: unknown) => toast.error(err instanceof Error ? err.message : "Could not load the workspace"));
  }, [applyList, refresh]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPalette((open) => !open);
      }
      if (event.key === "Escape") {
        setPalette(false);
        setMenu(false);
        setConnectOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const session = useMemo<Session>(
    () => ({
      principal,
      repos,
      connected,
      mode,
      oauth,
      github,
      installUrl,
      runs,
      refresh,
      connect,
      disconnect,
      refreshGithub,
      disconnectGithub,
    }),
    [principal, repos, connected, mode, oauth, github, installUrl, runs, refresh, connect, disconnect, refreshGithub, disconnectGithub],
  );

  return (
    <SessionContext.Provider value={session}>
      <div className="flex h-screen overflow-hidden bg-transparent text-[var(--ink)]">
        <aside className="hidden h-screen w-64 shrink-0 flex-col border-r border-[var(--line)] bg-[var(--card)] md:flex">
          <Sidebar
            connected={connected}
            runs={runs}
            theme={theme}
            onToggleTheme={toggle}
            onConnect={() => setConnectOpen(true)}
            principal={principal}
          />
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-14 items-center gap-2 border-b border-[var(--line)] px-3 md:hidden">
            <Button variant="ghost" size="icon" aria-label="Open menu" onClick={() => setMenu(true)}>
              <Menu className="h-4 w-4" />
            </Button>
            <span className="text-sm font-semibold">Factory</span>
          </header>
          <main className="min-h-0 flex-1 overflow-auto">
            <Outlet />
          </main>
        </div>
        {menu ? (
          <div className="fixed inset-0 z-40 bg-black/40 md:hidden" onClick={() => setMenu(false)}>
            <div className="h-full w-72 bg-[var(--card)] p-2" onClick={(event) => event.stopPropagation()}>
              <Sidebar
                connected={connected}
                runs={runs}
                theme={theme}
                onToggleTheme={toggle}
                onConnect={() => {
                  setMenu(false);
                  setConnectOpen(true);
                }}
                principal={principal}
                onNavigate={() => setMenu(false)}
              />
            </div>
          </div>
        ) : null}
        {palette ? (
          <Palette
            onClose={() => setPalette(false)}
            onPick={(path) => {
              setPalette(false);
              if (path === "theme") toggle();
              else if (path === "connect") setConnectOpen(true);
              else if (path === "compose") {
                navigate("/");
                document.querySelector<HTMLTextAreaElement>("[data-composer]")?.focus();
              } else navigate(path);
            }}
          />
        ) : null}
        {connectOpen ? (
          <ConnectDialog repos={repos} mode={mode} oauth={oauth} onClose={() => setConnectOpen(false)} onConnect={connect} />
        ) : null}
      </div>
    </SessionContext.Provider>
  );
}

function Sidebar({
  connected,
  runs,
  theme,
  principal,
  onToggleTheme,
  onConnect,
  onNavigate,
}: {
  connected: Repo | null;
  runs: RequestRow[];
  theme: "light" | "dark";
  principal: Principal | null;
  onToggleTheme: () => void;
  onConnect: () => void;
  onNavigate?: () => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 px-3 py-4">
        <span className="relative grid h-8 w-8 place-items-center">
          <span className="absolute h-7 w-7 rounded-full bg-[var(--accent)] opacity-90" />
          <span className="absolute h-5 w-5 translate-x-1 rounded-full bg-[var(--accent-2)] opacity-90" />
        </span>
        <div>
          <p className="wordmark text-sm font-semibold leading-none tracking-tight">Factory</p>
          <p className="mt-1 text-xs text-zinc-500">{principal?.id ?? "signed out"}</p>
        </div>
      </div>
      <button
        className="mx-2 flex items-center gap-2 rounded-md px-2 py-2 text-left text-sm hover:bg-zinc-100 dark:hover:bg-zinc-900"
        onClick={onConnect}
      >
        <FolderGit2 className="h-4 w-4 text-zinc-500" />
        <span className="min-w-0 truncate">{connected ? connected.full_name : "Connect a repository"}</span>
      </button>
      <nav className="mt-3 space-y-0.5 px-2">
        <Item to="/" label="New issue" icon={<Plus className="h-4 w-4" />} end onNavigate={onNavigate} />
        <Item to="/board" label="Board" icon={<ScrollText className="h-4 w-4" />} onNavigate={onNavigate} />
        <Item to="/inbox" label="Inbox" icon={<Inbox className="h-4 w-4" />} onNavigate={onNavigate} />
        <Item to="/runs" label="Runs" icon={<ScrollText className="h-4 w-4" />} onNavigate={onNavigate} />
        <Item to="/registry" label="Registry" icon={<Library className="h-4 w-4" />} onNavigate={onNavigate} />
        <Item to="/repos" label="Repositories" icon={<FolderGit2 className="h-4 w-4" />} onNavigate={onNavigate} />
        <Item to="/cost" label="Usage" icon={<CircleDollarSign className="h-4 w-4" />} onNavigate={onNavigate} />
        <Item to="/settings" label="Settings" icon={<Settings className="h-4 w-4" />} onNavigate={onNavigate} />
      </nav>
      <div className="mt-4 min-h-0 flex-1 overflow-auto px-2">
        <p className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-zinc-400">Recent</p>
        {distinct(runs).map((run) => (
          <NavLink
            key={run.id}
            to={`/runs/${run.id}`}
            onClick={onNavigate}
            className="block rounded-md px-2 py-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-900"
          >
            <span className="block truncate text-sm text-zinc-700 dark:text-zinc-300">{run.title}</span>
            <span className="text-[11px] text-zinc-400">{formatWhen(run.created_at)}</span>
          </NavLink>
        ))}
        {runs.length === 0 ? <p className="px-2 text-sm text-zinc-400">No runs yet.</p> : null}
      </div>
      <div className="flex items-center justify-between border-t border-zinc-200 p-2 dark:border-zinc-800">
        <span className="px-2 text-xs text-zinc-400">⌘K</span>
        <Button variant="ghost" size="icon" aria-label="Toggle theme" onClick={onToggleTheme}>
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </div>
    </div>
  );
}

function distinct(runs: RequestRow[]) {
  const seen = new Set<string>();
  const picked: RequestRow[] = [];
  for (const run of runs) {
    if (seen.has(run.title)) continue;
    seen.add(run.title);
    picked.push(run);
    if (picked.length === 6) break;
  }
  return picked;
}

function Item({
  to,
  label,
  icon,
  end,
  onNavigate,
}: {
  to: string;
  label: string;
  icon: ReactNode;
  end?: boolean;
  onNavigate?: () => void;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm",
          isActive ? "bg-[color-mix(in_srgb,var(--accent)_16%,transparent)] font-medium text-[var(--ink)]" : "text-zinc-600 hover:bg-black/5 dark:text-zinc-400 dark:hover:bg-white/5",
        )
      }
    >
      {icon}
      {label}
    </NavLink>
  );
}

function Palette({ onClose, onPick }: { onClose: () => void; onPick: (path: string) => void }) {
  const actions = [
    ["compose", "Describe an issue"],
    ["/board", "Go to the board"],
    ["/inbox", "Go to the inbox"],
    ["/runs", "Go to runs"],
    ["/registry", "Go to registry"],
    ["/repos", "Go to repositories"],
    ["/cost", "Go to usage"],
    ["/settings", "Go to settings"],
    ["connect", "Connect a repository"],
    ["theme", "Toggle theme"],
  ];
  return (
    <div className="fixed inset-0 z-50 bg-black/40" onClick={onClose}>
      <div
        className="mx-auto mt-24 w-[min(32rem,calc(100%-2rem))] overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-2xl dark:border-zinc-800 dark:bg-zinc-950"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-zinc-200 px-3 py-2 text-xs text-zinc-500 dark:border-zinc-800">
          Command
          <button aria-label="Close" onClick={onClose}>
            <X className="h-4 w-4" />
          </button>
        </div>
        {actions.map(([id, label]) => (
          <button
            key={id}
            className="block w-full px-3 py-2 text-left text-sm hover:bg-zinc-100 dark:hover:bg-zinc-900"
            onClick={() => onPick(id)}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

function ConnectDialog({
  repos,
  mode,
  oauth,
  onClose,
  onConnect,
}: {
  repos: Repo[];
  mode: string;
  oauth: boolean;
  onClose: () => void;
  onConnect: (fullName: string) => Promise<void>;
}) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-xl border border-zinc-200 bg-white p-5 shadow-xl dark:border-zinc-800 dark:bg-zinc-950"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="text-base font-semibold">Connect a repository</h2>
        <p className="mt-1 text-sm text-zinc-500">
          {mode === "github-app"
            ? "The GitHub App is configured. You can also work in the local sample."
            : "No GitHub App is configured. Connect the bundled sample to run the full demo."}
        </p>
        <div className="mt-4 space-y-2">
          {repos.map((repo) => (
            <button
              key={repo.full_name}
              className="flex w-full items-start justify-between gap-3 rounded-lg border border-zinc-200 px-3 py-3 text-left hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
              onClick={() => void onConnect(repo.full_name)}
            >
              <span>
                <span className="block text-sm font-medium">{repo.full_name}</span>
                <span className="mt-1 block text-xs text-zinc-500">{repo.description}</span>
              </span>
              <span className="text-xs uppercase text-zinc-400">{repo.kind}</span>
            </button>
          ))}
        </div>
        {oauth ? (
          <a className="mt-4 inline-flex text-sm font-medium underline" href="/api/auth/github/login">
            Connect GitHub
          </a>
        ) : (
          <p className="mt-4 text-sm text-zinc-500">
            GitHub sign-in needs the OAuth app. See{" "}
            <Link to="/settings#github" className="font-medium text-[var(--accent)] underline" onClick={onClose}>
              Settings → GitHub
            </Link>
            .
          </p>
        )}
      </div>
    </div>
  );
}

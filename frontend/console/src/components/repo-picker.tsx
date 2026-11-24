import { filterRepos, GITHUB_OAUTH_NOTE } from "@/lib/repo-picker";
import type { Repo } from "@/lib/types";
import { Check, ChevronDown, Github } from "lucide-react";
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";

export function RepoPicker({
  repos,
  connected,
  oauth,
  open,
  onOpenChange,
  onSelect,
}: {
  repos: Repo[];
  connected: Repo | null;
  oauth: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (fullName: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const listId = useId();
  const noteId = useId();
  const filtered = filterRepos(repos, query);
  const selected = connected?.full_name ? connected : null;
  const label = selected?.full_name ?? "Choose repository";

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActive(0);
    const timer = window.setTimeout(() => searchRef.current?.focus(), 0);
    function onPointer(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) onOpenChange(false);
    }
    document.addEventListener("mousedown", onPointer);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener("mousedown", onPointer);
    };
  }, [open, onOpenChange]);

  function choose(fullName: string) {
    onSelect(fullName);
    onOpenChange(false);
    buttonRef.current?.focus();
  }

  function onSearchKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index) => Math.min(index + 1, Math.max(filtered.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const repo = filtered[active];
      if (repo) choose(repo.full_name);
    } else if (event.key === "Escape") {
      event.preventDefault();
      onOpenChange(false);
      buttonRef.current?.focus();
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-label={selected ? `Repository ${selected.full_name}` : "Choose repository"}
        onClick={() => onOpenChange(!open)}
        className="inline-flex max-w-[16rem] items-center gap-1.5 rounded-full border border-[var(--line)] bg-white/80 px-2.5 py-1 text-xs text-[var(--ink)] hover:border-[var(--accent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] dark:bg-white/5"
      >
        <Github className="h-3.5 w-3.5 shrink-0 text-[var(--accent)]" aria-hidden="true" />
        <span className="truncate">{label}</span>
        <ChevronDown className="h-3 w-3 shrink-0 text-zinc-400" aria-hidden="true" />
      </button>
      {open ? (
        <div
          id={listId}
          role="dialog"
          aria-label="Choose repository"
          className="absolute bottom-full left-0 z-30 mb-2 w-80 rounded-xl border border-[var(--line)] bg-[#fffdf8] p-2 shadow-xl dark:bg-[#121c18]"
        >
          <input
            ref={searchRef}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setActive(0);
            }}
            onKeyDown={onSearchKey}
            placeholder="Search repositories"
            aria-label="Search repositories"
            aria-controls={`${listId}-options`}
            className="h-8 w-full rounded-lg border border-[var(--line)] bg-transparent px-2 text-sm outline-none focus:border-[var(--accent)]"
          />
          <ul id={`${listId}-options`} role="listbox" aria-label="Repositories" className="mt-2 max-h-52 space-y-0.5 overflow-auto">
            {filtered.map((repo, index) => {
              const current = selected?.full_name === repo.full_name;
              return (
                <li key={repo.full_name}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={current}
                    onMouseEnter={() => setActive(index)}
                    onClick={() => choose(repo.full_name)}
                    className={`flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left text-sm ${index === active ? "bg-[color-mix(in_srgb,var(--accent)_14%,transparent)]" : ""}`}
                  >
                    <Github className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--accent)]" aria-hidden="true" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{repo.full_name}</span>
                      <span className="block truncate text-xs text-zinc-500">
                        {repo.kind === "local" ? "Local sample" : repo.description}
                      </span>
                    </span>
                    {current ? <Check className="mt-0.5 h-3.5 w-3.5 text-[var(--accent)]" aria-hidden="true" /> : null}
                  </button>
                </li>
              );
            })}
            {filtered.length === 0 ? <li className="px-2 py-3 text-sm text-zinc-500">No repositories match.</li> : null}
          </ul>
          <div className="mt-2 border-t border-[var(--line)] pt-2">
            {oauth ? (
              <a
                href="/api/auth/github/login"
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-medium text-white"
              >
                <Github className="h-4 w-4" aria-hidden="true" />
                Connect GitHub
              </a>
            ) : (
              <>
                <button
                  type="button"
                  aria-describedby={noteId}
                  className="flex w-full items-center justify-center gap-2 rounded-lg border border-[var(--accent-2)] px-3 py-2 text-sm font-medium text-[var(--accent-2)]"
                >
                  <Github className="h-4 w-4" aria-hidden="true" />
                  Connect GitHub
                </button>
                <p id={noteId} className="mt-2 text-xs leading-5 text-zinc-500">
                  {GITHUB_OAUTH_NOTE} See{" "}
                  <Link to="/settings#github" className="font-medium text-[var(--accent)] underline" onClick={() => onOpenChange(false)}>
                    Settings → GitHub
                  </Link>
                  . The local sample stays available.
                </p>
              </>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

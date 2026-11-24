import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useAssistantState,
  useComposerRuntime,
  useLocalRuntime,
  type ChatModelAdapter,
} from "@assistant-ui/react";
import { BranchChip, RepoPicker } from "@/components/repo-picker";
import { RunPanel } from "@/components/run-panel";
import { useSession } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { issueTarget } from "@/lib/repo-picker";
import { motion } from "framer-motion";
import { ArrowUp, Github } from "lucide-react";
import { useState } from "react";

const SUGGESTIONS = [
  {
    title: "Billing",
    detail: "Add Apple Pay to the billing portal",
    text: "Add Apple Pay to the billing portal",
  },
  {
    title: "Access",
    detail: "Require SSO before an admin can change roles",
    text: "Require SSO before an admin can change roles",
  },
  {
    title: "Accounts",
    detail: "Show contract renewal dates on the account page",
    text: "Show contract renewal dates on the account page",
  },
];

const bridge: { target: () => Promise<string | null>; refresh: () => Promise<void> } = {
  target: async () => null,
  refresh: async () => undefined,
};

export function setChatTarget(target: () => Promise<string | null>) {
  bridge.target = target;
}

export function setChatRefresh(refresh: () => Promise<void>) {
  bridge.refresh = refresh;
}

const adapter: ChatModelAdapter = {
  async run({ messages }) {
    const last = messages.at(-1);
    const part = last?.content.find((item) => item.type === "text");
    const text = part && "text" in part ? part.text.trim() : "";
    const body = text || "Add a health check";
    const target = await bridge.target();
    if (!target) {
      return { content: [{ type: "text" as const, text: "Choose a repository to send this issue." }] };
    }
    const created = await api.createRequest(body.slice(0, 80), body, target);
    const done = new Set(["completed", "failed", "killed", "parked", "awaiting_approval"]);
    for (let attempt = 0; attempt < 20; attempt += 1) {
      const view = await api.view(created.id);
      if (done.has(view.request.status)) break;
      await new Promise((resolve) => setTimeout(resolve, 200));
    }
    await bridge.refresh();
    return { content: [{ type: "text" as const, text: `Working on it.\n\nrun:${created.id}` }] };
  },
};

export function ChatThread() {
  const runtime = useLocalRuntime(adapter);
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ThreadPrimitive.Root className="flex h-full min-h-0 flex-col">
        <ThreadPrimitive.Viewport className="min-h-0 flex-1 overflow-auto px-6 py-10">
          <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
            <ThreadPrimitive.Empty>
              <EmptyState />
            </ThreadPrimitive.Empty>
            <ThreadPrimitive.Messages
              components={{
                UserMessage: UserBubble,
                AssistantMessage: AssistantBubble,
              }}
            />
          </div>
        </ThreadPrimitive.Viewport>
        <ComposerBar />
      </ThreadPrimitive.Root>
    </AssistantRuntimeProvider>
  );
}

function ComposerBar() {
  const session = useSession();
  const [open, setOpen] = useState(false);
  const [hint, setHint] = useState(false);
  const selected = session.connected?.full_name ? session.connected : null;
  const ready = Boolean(issueTarget(selected));

  return (
    <div className="px-4 pb-4">
      {session.oauth && !session.github ? (
        <div className="mx-auto mb-2 flex w-full max-w-3xl items-center justify-between gap-3 rounded-xl border border-[var(--line)] px-3 py-2">
          <p className="text-sm">Connect GitHub to use repositories you grant to the app.</p>
          <a href="/api/auth/github/login" className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white">
            <Github className="h-3.5 w-3.5" aria-hidden="true" />
            Connect GitHub
          </a>
        </div>
      ) : null}
      {session.oauth ? null : (
        <div className="mx-auto mb-2 flex w-full max-w-3xl items-center justify-between gap-3 rounded-xl border border-[var(--line)] bg-[color-mix(in_srgb,var(--accent-2)_12%,transparent)] px-3 py-2">
          <p className="text-sm">GitHub isn't connected. The local sample still runs.</p>
          <button
            type="button"
            className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white"
            onClick={() => setOpen(true)}
          >
            <Github className="h-3.5 w-3.5" aria-hidden="true" />
            Connect GitHub
          </button>
        </div>
      )}
      <ComposerPrimitive.Root className="surface mx-auto flex w-full max-w-4xl flex-col rounded-xl p-3">
        <ComposerPrimitive.Input
          data-composer
          placeholder="Describe the issue"
          submitOnEnter={ready}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !ready) setHint(true);
          }}
          className="max-h-40 min-h-16 w-full resize-none bg-transparent px-2 py-2 text-sm outline-none"
        />
        <div className="flex flex-wrap items-center justify-between gap-2 px-1 pt-1">
          <RepoPicker
            repos={session.repos}
            connected={selected}
            oauth={session.oauth}
            github={session.github}
            installUrl={session.installUrl}
            open={open}
            onOpenChange={setOpen}
            onRefresh={() => void session.refreshGithub()}
            onDisconnect={() => void session.disconnectGithub()}
            onSelect={(fullName) => {
              setHint(false);
              void session.connect(fullName);
            }}
          />
          {selected?.kind === "github" ? (
            <BranchChip
              name={selected.branch || selected.default_branch || "main"}
              load={() => api.branches(selected.full_name)}
              onSelect={(branch) => void session.connect(selected.full_name, branch)}
            />
          ) : null}
          {ready ? (
            <ComposerPrimitive.Send asChild>
              <Button size="icon" aria-label="Send">
                <ArrowUp className="h-4 w-4" />
              </Button>
            </ComposerPrimitive.Send>
          ) : (
            <Button size="icon" aria-label="Send" type="button" onClick={() => setHint(true)}>
              <ArrowUp className="h-4 w-4" />
            </Button>
          )}
        </div>
        {hint && !ready ? (
          <p role="status" className="px-2 pt-1 text-xs text-[var(--accent-2)]">
            Choose a repository to send this issue.
          </p>
        ) : null}
      </ComposerPrimitive.Root>
      <p className="mx-auto mt-2 max-w-4xl text-xs text-zinc-400">Enter to send. ⌘K opens commands.</p>
    </div>
  );
}

function EmptyState() {
  const composer = useComposerRuntime();
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex min-h-[46vh] flex-col justify-center">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-zinc-500">New issue</p>
      <h1 className="mt-3 max-w-2xl text-4xl font-semibold tracking-tight">What should we change?</h1>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-500">
        Describe the outcome. The factory reads the repository, asks when needed, and verifies the change. Pull requests stay yours to merge.
      </p>
      <div className="mt-8 grid gap-3 sm:grid-cols-3">
        {SUGGESTIONS.map((item) => (
          <button
            key={item.title}
            className="surface rounded-xl px-4 py-4 text-left transition hover:border-[#1f3a5f]"
            onClick={() => composer.setText(item.text)}
          >
            <span className="text-xs font-semibold uppercase tracking-wide text-[#1f3a5f] dark:text-[#8fb4e0]">{item.title}</span>
            <span className="mt-2 block text-sm leading-5">{item.detail}</span>
          </button>
        ))}
      </div>
    </motion.div>
  );
}

function UserBubble() {
  return (
    <div className="ml-auto max-w-[85%] rounded-lg bg-[#1f3a5f] px-4 py-2.5 text-sm text-white">
      <MessagePrimitive.Content />
    </div>
  );
}

function AssistantBubble() {
  const text = useAssistantState(({ message }) =>
    message.content
      .map((part) => (part.type === "text" && "text" in part ? part.text : ""))
      .join("\n"),
  );
  const match = text.match(/run:([0-9a-f-]{36})/i);
  if (!match) {
    return (
      <div className="max-w-[90%] text-sm leading-6">
        <MessagePrimitive.Content />
      </div>
    );
  }
  return (
    <div className="w-full">
      <p className="mb-3 text-sm">Here is the run.</p>
      <RunPanel id={match[1]} />
    </div>
  );
}

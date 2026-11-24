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
  "Add Apple Pay to the billing portal",
  "Require SSO before an admin can change roles",
  "Show contract renewal dates on the account page",
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
        <ThreadPrimitive.Viewport className="min-h-0 flex-1 overflow-auto px-4 py-8">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
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
      <ComposerPrimitive.Root className="surface mx-auto flex w-full max-w-3xl flex-col rounded-2xl p-2">
        <ComposerPrimitive.Input
          data-composer
          placeholder="Describe the issue"
          submitOnEnter={ready}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !ready) setHint(true);
          }}
          className="max-h-40 min-h-11 w-full resize-none bg-transparent px-2 py-2 text-sm outline-none"
        />
        <div className="flex items-center justify-between gap-2 px-1 pt-1">
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
      <p className="mx-auto mt-2 max-w-3xl text-center text-xs text-zinc-400">Enter to send · ⌘K for commands</p>
    </div>
  );
}

function EmptyState() {
  const composer = useComposerRuntime();
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex min-h-[46vh] flex-col justify-center">
      <div className="mb-5 flex items-center gap-3">
        <span className="relative grid h-10 w-10 place-items-center">
          <span className="absolute h-9 w-9 rounded-full bg-[var(--accent)]" />
          <span className="absolute h-6 w-6 translate-x-1.5 rounded-full bg-[var(--accent-2)]" />
        </span>
        <p className="wordmark text-sm font-semibold tracking-tight">Factory</p>
      </div>
      <h1 className="wordmark text-4xl font-semibold tracking-tight">What should we change?</h1>
      <p className="mt-3 max-w-lg text-sm leading-6 text-zinc-500">
        Describe the issue. A crew plans the work, checks it, and opens a pull request. It never merges.
      </p>
      <div className="mt-6 flex flex-wrap gap-2">
        {SUGGESTIONS.map((text) => (
          <button
            key={text}
            className="surface rounded-full px-3 py-1.5 text-left text-sm hover:border-[var(--accent)]"
            onClick={() => composer.setText(text)}
          >
            {text}
          </button>
        ))}
      </div>
    </motion.div>
  );
}

function UserBubble() {
  return (
    <div className="ml-auto max-w-[85%] rounded-2xl bg-[var(--accent)] px-4 py-2.5 text-sm text-white">
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

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
import { RunPanel } from "@/components/run-panel";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { motion } from "framer-motion";
import { ArrowUp } from "lucide-react";

const SUGGESTIONS = [
  "Show coupon expiry in the cart",
  "Add Apple Pay to the receipt sheet",
  "Split the checkout form into two steps",
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
        <div className="px-4 pb-4">
          <ComposerPrimitive.Root className="surface mx-auto flex w-full max-w-3xl items-end gap-2 rounded-2xl p-2">
            <ComposerPrimitive.Input
              data-composer
              placeholder="Describe the issue"
              className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none"
            />
            <ComposerPrimitive.Send asChild>
              <Button size="icon" aria-label="Send">
                <ArrowUp className="h-4 w-4" />
              </Button>
            </ComposerPrimitive.Send>
          </ComposerPrimitive.Root>
          <p className="mx-auto mt-2 max-w-3xl text-center text-xs text-zinc-400">Enter to send · ⌘K for commands</p>
        </div>
      </ThreadPrimitive.Root>
    </AssistantRuntimeProvider>
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

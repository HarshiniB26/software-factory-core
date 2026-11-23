import { api } from "@/lib/api";
import { money, repoLabel } from "@/lib/format";
import type { BoardCard } from "@/lib/types";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

const COLUMNS = [
  ["queued", "Queued"],
  ["planning", "Planning"],
  ["needs_input", "Needs input"],
  ["building", "Building"],
  ["gates", "Gates"],
  ["pr", "PR open"],
  ["done", "Done"],
] as const;

export function BoardPage() {
  const [items, setItems] = useState<BoardCard[] | null>(null);
  useEffect(() => {
    const load = () => api.board().then((payload) => setItems(payload.items)).catch(() => setItems([]));
    void load();
    const timer = window.setInterval(load, 4000);
    return () => window.clearInterval(timer);
  }, []);
  return (
    <div className="px-6 py-8">
      <h1 className="wordmark text-2xl font-semibold tracking-tight">Board</h1>
      <p className="mt-1 text-sm text-zinc-500">Jobs move from the queue to an open pull request. Nothing here merges.</p>
      {items === null ? <div className="mt-6 h-64 animate-pulse rounded-2xl bg-white/50 dark:bg-white/5" /> : null}
      {items ? (
        <div className="mt-6 flex gap-3 overflow-auto pb-4">
          {COLUMNS.map(([id, label]) => {
            const cards = items.filter((item) => item.stage === id);
            return (
              <section key={id} className="surface w-64 shrink-0 rounded-2xl p-3">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="text-sm font-medium">{label}</h2>
                  <span className="text-xs text-zinc-500">{cards.length}</span>
                </div>
                <div className="space-y-2">
                  {cards.map((card, index) => (
                    <motion.div key={card.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.03 }}>
                      <Link to={`/runs/${card.id}`} className="block rounded-xl bg-white/80 p-3 text-sm shadow-sm ring-1 ring-black/5 dark:bg-black/20 dark:ring-white/10">
                        <p className="font-medium leading-5">{card.title}</p>
                        <p className="mt-2 text-xs text-zinc-500">{repoLabel(card.target)} · {card.model ?? "model pending"}</p>
                        <p className="text-xs text-[var(--accent)]">{money(card.cost_usd)}</p>
                      </Link>
                    </motion.div>
                  ))}
                  {cards.length === 0 ? <p className="px-1 text-xs text-zinc-400">Nothing in this stage.</p> : null}
                </div>
              </section>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

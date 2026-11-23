import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

const tones = {
  neutral: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  run: "bg-sky-50 text-sky-800 dark:bg-sky-950 dark:text-sky-200",
  wait: "bg-amber-50 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  ok: "bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
  bad: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-200",
};

export function Badge({
  tone = "neutral",
  children,
  className,
}: {
  tone?: keyof typeof tones;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", tones[tone], className)}>
      {children}
    </span>
  );
}

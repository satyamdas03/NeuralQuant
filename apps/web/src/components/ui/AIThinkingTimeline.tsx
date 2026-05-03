"use client";

import { Check, Loader2 } from "lucide-react";

export type PhaseEntry = {
  phase: string;
  label: string;
  startedAt: number;        // ms epoch
  completedAt?: number;     // ms epoch — undefined if still active
};

type Props = {
  phases: PhaseEntry[];
};

/**
 * Vertical AI thinking timeline (Claude/ChatGPT style).
 * Each phase is a row: [icon] [label] [elapsed ms].
 * Currently active phase shows a spinning loader; completed phases show a check.
 * The component mounts as soon as the first phase event arrives.
 */
export default function AIThinkingTimeline({ phases }: Props) {
  if (phases.length === 0) return null;

  // eslint-disable-next-line react-hooks/purity -- Date.now is needed for real-time elapsed calculation
  const now = Date.now();
  const activeIdx = phases.findIndex((p) => p.completedAt === undefined);
  const totalElapsed = phases[0]
    ? Math.round(((phases[phases.length - 1].completedAt ?? now) - phases[0].startedAt) / 100) / 10
    : 0;

  return (
    <div className="rounded-xl bg-surface-low ghost-border p-4 space-y-2.5">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[11px] font-medium uppercase tracking-wider text-on-surface-variant">
          AI is working
        </span>
        <span className="text-[11px] tabular-nums text-on-surface-variant">
          {totalElapsed.toFixed(1)}s
        </span>
      </div>

      <ol className="space-y-2">
        {phases.map((p, i) => {
          const isActive = i === activeIdx;
          const isDone = p.completedAt !== undefined;
          const elapsed = isDone
            ? Math.round((p.completedAt! - p.startedAt) / 100) / 10
            : Math.round((now - p.startedAt) / 100) / 10;

          return (
            <li key={`${p.phase}-${i}`} className="flex items-start gap-3">
              <div className="mt-0.5 flex h-5 w-5 items-center justify-center">
                {isActive ? (
                  <Loader2 size={14} className="animate-spin text-primary" />
                ) : isDone ? (
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-tertiary/20">
                    <Check size={11} className="text-tertiary" strokeWidth={3} />
                  </span>
                ) : (
                  <span className="h-1.5 w-1.5 rounded-full bg-on-surface-variant/40" />
                )}
              </div>
              <div className="flex-1 flex items-center justify-between gap-2 min-w-0">
                <span
                  className={`text-sm truncate ${
                    isActive
                      ? "text-on-surface font-medium"
                      : isDone
                      ? "text-on-surface-variant"
                      : "text-on-surface-variant/60"
                  }`}
                >
                  {p.label}
                </span>
                <span
                  className={`text-[10px] tabular-nums shrink-0 ${
                    isActive ? "text-primary" : "text-on-surface-variant/70"
                  }`}
                >
                  {elapsed.toFixed(1)}s
                </span>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

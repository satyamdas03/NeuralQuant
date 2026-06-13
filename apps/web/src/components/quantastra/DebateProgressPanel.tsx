"use client";

import { useEffect, useState } from "react";
import { Check, Loader2, BrainCircuit } from "lucide-react";

const ANALYSTS = [
  "Macro",
  "Fundamental",
  "Technical",
  "Sentiment",
  "Geopolitical",
  "Adversarial",
] as const;

export interface DebateState {
  ticker: string;
  phase: "started" | "complete" | "error";
  verdict?: string | null;
  consensusScore?: number | null;
}

// Reveal the 6 parallel analysts over ~24s, then hold on Head Analyst until `complete`.
export default function DebateProgressPanel({ state }: { state: DebateState }) {
  const [revealed, setRevealed] = useState(0);

  useEffect(() => {
    if (state.phase !== "started") {
      setRevealed(ANALYSTS.length);
      return;
    }
    setRevealed(0);
    const timers = ANALYSTS.map((_, i) =>
      setTimeout(() => setRevealed((r) => Math.max(r, i + 1)), (i + 1) * 4000)
    );
    return () => timers.forEach(clearTimeout);
  }, [state.phase, state.ticker]);

  const done = state.phase === "complete";
  const failed = state.phase === "error";

  return (
    <div className="mx-auto my-4 w-full max-w-sm rounded-lg border border-ghost-border bg-surface-container/40 p-4">
      <div className="mb-3 flex items-center gap-2">
        <BrainCircuit size={16} className="text-primary-fixed" />
        <span className="text-xs font-mono uppercase tracking-wider text-on-surface">
          PARA-DEBATE · {state.ticker}
        </span>
      </div>

      <ul className="space-y-1.5">
        {ANALYSTS.map((name, i) => {
          const active = !done && !failed && i === revealed;
          const finished = done || i < revealed;
          return (
            <li key={name} className="flex items-center gap-2 text-xs">
              {finished ? (
                <Check size={13} className="text-primary-fixed" />
              ) : active ? (
                <Loader2 size={13} className="animate-spin text-primary" />
              ) : (
                <span className="inline-block h-[13px] w-[13px] rounded-full border border-ghost-border" />
              )}
              <span className={finished ? "text-on-surface" : "text-on-surface-variant"}>
                {name} analyst
              </span>
            </li>
          );
        })}
        <li className="mt-1 flex items-center gap-2 border-t border-ghost-border pt-2 text-xs">
          {done ? (
            <Check size={13} className="text-primary-fixed" />
          ) : failed ? (
            <span className="inline-block h-[13px] w-[13px] rounded-full border border-error" />
          ) : (
            <Loader2 size={13} className="animate-spin text-primary" />
          )}
          <span className="font-medium text-on-surface">
            {done ? "Head Analyst — verdict ready" : failed ? "Analysis unavailable" : "Head Analyst synthesizing…"}
          </span>
        </li>
      </ul>

      {done && state.verdict && (
        <p className="mt-3 text-center text-sm font-bold text-primary-fixed">
          {state.verdict}
          {state.consensusScore != null && (
            <span className="ml-2 font-mono text-xs text-on-surface-variant">
              consensus {state.consensusScore}
            </span>
          )}
        </p>
      )}
    </div>
  );
}

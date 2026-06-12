"use client";

import { Mic, MicOff, Moon, Sparkles } from "lucide-react";

export type OrbState =
  | "idle"          // never enabled this session
  | "connecting"
  | "listening"
  | "speaking"
  | "quiet"         // yielding to Astra/Morgan
  | "sleeping"      // idle-disconnected
  | "capped"        // daily cap hit
  | "unavailable";  // hard error

const LABELS: Record<OrbState, string> = {
  idle: "Meet Veronica",
  connecting: "Connecting…",
  listening: "Listening",
  speaking: "Veronica",
  quiet: "Quiet",
  sleeping: "Tap to wake Veronica",
  capped: "Back tomorrow",
  unavailable: "Veronica unavailable",
};

export default function VeronicaOrb({
  state,
  hint,
  onClick,
}: {
  state: OrbState;
  hint?: string | null;
  onClick: () => void;
}) {
  const active = state === "listening" || state === "speaking";
  return (
    <div className="fixed bottom-20 right-4 z-[60] flex flex-col items-end gap-2 md:bottom-6 md:right-6">
      {hint && (
        <div className="glass-strong ghost-border max-w-[220px] rounded-xl px-3 py-2 text-xs text-on-surface">
          {hint}
        </div>
      )}
      <button
        onClick={onClick}
        aria-label={LABELS[state]}
        title={LABELS[state]}
        className={[
          "flex size-14 items-center justify-center rounded-full transition-all",
          active
            ? "bg-primary-fixed text-background shadow-[0_0_25px_rgba(0,255,178,0.45)]"
            : "",
          state === "speaking" ? "animate-pulse" : "",
          state === "idle"
            ? "bg-primary-fixed/15 text-primary-fixed ring-1 ring-primary-fixed/40 animate-pulse"
            : "",
          state === "connecting"
            ? "bg-primary-fixed/15 text-primary-fixed ring-1 ring-primary-fixed/40 animate-pulse"
            : "",
          state === "quiet" || state === "sleeping"
            ? "bg-surface-high text-on-surface-variant ring-1 ring-ghost-border"
            : "",
          state === "capped" || state === "unavailable"
            ? "bg-surface-high text-on-surface-variant/50 ring-1 ring-ghost-border"
            : "",
        ].join(" ")}
      >
        {state === "quiet" ? (
          <MicOff className="size-6" />
        ) : state === "sleeping" ? (
          <Moon className="size-6" />
        ) : state === "idle" ? (
          <Sparkles className="size-6" />
        ) : (
          <Mic className="size-6" />
        )}
      </button>
    </div>
  );
}

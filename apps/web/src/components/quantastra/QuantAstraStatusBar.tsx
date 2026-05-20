"use client";

type AgentState = "initializing" | "idle" | "listening" | "thinking" | "speaking";

const STATE_CONFIG: Record<AgentState, { label: string; color: string; pulse: boolean }> = {
  initializing: { label: "Connecting...", color: "bg-amber-400", pulse: true },
  idle: { label: "Ready", color: "bg-emerald-400", pulse: false },
  listening: { label: "Listening", color: "bg-sky-400", pulse: true },
  thinking: { label: "Thinking", color: "bg-amber-400", pulse: true },
  speaking: { label: "Speaking", color: "bg-primary-fixed", pulse: false },
};

export default function QuantAstraStatusBar({ state }: { state: AgentState }) {
  const config = STATE_CONFIG[state] || STATE_CONFIG.idle;

  return (
    <div className="flex items-center gap-2 rounded-full bg-surface-high/60 px-4 py-1.5 backdrop-blur">
      <span className="relative flex size-2.5">
        <span
          className={`absolute inline-flex size-full rounded-full ${config.color} ${
            config.pulse ? "animate-ping opacity-75" : ""
          }`}
        />
        <span
          className={`relative inline-flex size-2.5 rounded-full ${config.color}`}
        />
      </span>
      <span className="text-xs font-medium text-on-surface">
        {config.label}
      </span>
    </div>
  );
}

"use client";
import { useState } from "react";
import type { AgentOutput, AnalystResponse } from "@/lib/types";
import GlassPanel from "@/components/ui/GlassPanel";

const STANCE_COLORS: Record<string, string> = {
  BULL:    "text-tertiary bg-tertiary/10 ghost-border",
  BEAR:    "text-error bg-error/10 ghost-border",
  NEUTRAL: "text-secondary bg-secondary/10 ghost-border",
};

const VERDICT_COLORS: Record<string, string> = {
  "STRONG BUY":  "text-tertiary bg-tertiary/20",
  "BUY":         "text-tertiary bg-tertiary/10",
  "HOLD":        "text-secondary bg-secondary/10",
  "SELL":        "text-error bg-error/10",
  "STRONG SELL": "text-error bg-error/20",
};

function AgentCard({ output }: { output: AgentOutput }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="ghost-border rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 hover:bg-surface-high transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-on-surface-variant w-24">{output.agent}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${STANCE_COLORS[output.stance] ?? "text-on-surface-variant"}`}>
            {output.stance}
          </span>
          <span className="text-xs text-on-surface-variant">{output.conviction}</span>
        </div>
        <span className="text-on-surface-variant text-sm">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-3 bg-surface-container/30">
          <p className="text-sm text-on-surface">{output.thesis}</p>
          <ul className="space-y-1">
            {output.key_points.map((p, i) => (
              <li key={i} className="text-xs text-on-surface-variant flex gap-2">
                <span className="text-primary flex-shrink-0">—</span>{p}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function AgentDebatePanel({ report }: { report: AnalystResponse }) {
  return (
    <div className="space-y-4">
      <GlassPanel>
        <p className="text-xs text-on-surface-variant uppercase tracking-wider mb-2">Head Analyst Verdict</p>
        <div className={`inline-flex px-4 py-2 rounded-full text-lg font-bold mb-3 ${VERDICT_COLORS[report.head_analyst_verdict] ?? ""}`}>
          {report.head_analyst_verdict}
        </div>
        <p className="text-sm text-on-surface">{report.investment_thesis}</p>
      </GlassPanel>

      <GlassPanel>
        <p className="text-xs text-on-surface-variant uppercase tracking-wider mb-4">PARA-DEBATE Panel</p>
        <div className="space-y-2">
          {report.agent_outputs.map((o) => <AgentCard key={o.agent} output={o} />)}
        </div>
      </GlassPanel>

      <GlassPanel>
        <p className="text-xs text-on-surface-variant uppercase tracking-wider mb-3">Risk Factors</p>
        <ul className="space-y-2">
          {report.risk_factors.map((r, i) => (
            <li key={i} className="flex gap-2 text-sm text-on-surface">
              <span className="text-error flex-shrink-0">⚠</span>{r}
            </li>
          ))}
        </ul>
      </GlassPanel>
    </div>
  );
}
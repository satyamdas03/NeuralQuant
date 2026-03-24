"use client";
import { useState } from "react";
import type { AgentOutput, AnalystResponse } from "@/lib/types";

const STANCE_COLORS = {
  BULL:    "text-green-400 bg-green-500/10 border-green-500/20",
  BEAR:    "text-red-400 bg-red-500/10 border-red-500/20",
  NEUTRAL: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20",
};

const VERDICT_COLORS: Record<string, string> = {
  "STRONG BUY":  "text-green-300 bg-green-500/20",
  "BUY":         "text-green-400 bg-green-500/10",
  "HOLD":        "text-yellow-400 bg-yellow-500/10",
  "SELL":        "text-red-400 bg-red-500/10",
  "STRONG SELL": "text-red-300 bg-red-500/20",
};

function AgentCard({ output }: { output: AgentOutput }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-gray-800 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 hover:bg-gray-800/40 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-gray-500 w-24">{output.agent}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full border ${STANCE_COLORS[output.stance]}`}>
            {output.stance}
          </span>
          <span className="text-xs text-gray-500">{output.conviction}</span>
        </div>
        <span className="text-gray-600 text-sm">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-3 bg-gray-900/30">
          <p className="text-sm text-gray-300">{output.thesis}</p>
          <ul className="space-y-1">
            {output.key_points.map((p, i) => (
              <li key={i} className="text-xs text-gray-400 flex gap-2">
                <span className="text-violet-500 flex-shrink-0">—</span>{p}
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
      <div className="p-5 rounded-2xl border border-gray-800 bg-gray-900/60">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Head Analyst Verdict</p>
        <div className={`inline-flex px-4 py-2 rounded-full text-lg font-bold mb-3 ${VERDICT_COLORS[report.head_analyst_verdict] ?? ""}`}>
          {report.head_analyst_verdict}
        </div>
        <p className="text-sm text-gray-300">{report.investment_thesis}</p>
      </div>

      <div className="p-5 rounded-2xl border border-gray-800 bg-gray-900/60">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-4">PARA-DEBATE Panel</p>
        <div className="space-y-2">
          {report.agent_outputs.map((o) => <AgentCard key={o.agent} output={o} />)}
        </div>
      </div>

      <div className="p-5 rounded-2xl border border-gray-800 bg-gray-900/60">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">Risk Factors</p>
        <ul className="space-y-2">
          {report.risk_factors.map((r, i) => (
            <li key={i} className="flex gap-2 text-sm text-gray-300">
              <span className="text-red-500 flex-shrink-0">⚠</span>{r}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import type { AIScore, AgentOutput, AnalystResponse, SubScores } from "@/lib/types";
import GlassPanel from "@/components/ui/GlassPanel";
import { Database, BarChart3, BrainCircuit } from "lucide-react";

function FactorBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-on-surface w-28 flex-shrink-0">{label}</span>
      <div className="flex-1 h-2.5 bg-surface-high rounded-full overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-primary to-secondary transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-on-surface-variant w-10 text-right font-mono tabular-nums">
        {pct}
      </span>
    </div>
  );
}

function AgentReasonCard({ output }: { output: AgentOutput }) {
  const [open, setOpen] = useState(false);
  const stanceColor =
    output.stance === "BULL"
      ? "text-tertiary bg-tertiary/10"
      : output.stance === "BEAR"
      ? "text-error bg-error/10"
      : "text-secondary bg-secondary/10";
  return (
    <div className="ghost-border rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-3 hover:bg-surface-high transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-on-surface-variant w-20">{output.agent}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${stanceColor}`}>{output.stance}</span>
          <span className="text-xs text-on-surface-variant">{output.conviction}</span>
        </div>
        <span className="text-on-surface-variant text-xs">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-2 bg-surface-container/30">
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

function ScoreBreakdownBars({ scores }: { scores: SubScores }) {
  return (
    <div className="space-y-3">
      <FactorBar label="Quality" value={scores.quality} />
      <FactorBar label="Momentum" value={scores.momentum} />
      <FactorBar label="Value" value={scores.value} />
      <FactorBar label="Low Vol" value={scores.low_vol} />
      <FactorBar label="Short Interest" value={scores.short_interest} />
      {scores.insider !== undefined && scores.insider !== 0.5 && (
        <FactorBar label="Insider" value={scores.insider} />
      )}
    </div>
  );
}

interface TransparencyPanelProps {
  score: AIScore;
  report?: AnalystResponse | null;
}

export function TransparencyPanel({ score, report }: TransparencyPanelProps) {
  const dataSources =
    score.market === "US"
      ? [
          "yfinance (prices & fundamentals)",
          "FRED (macro indicators)",
          "EDGAR (insider filings)",
        ]
      : score.market === "IN"
      ? [
          "yfinance (prices & fundamentals)",
          "NSE Bhavcopy (market data)",
          "FRED (macro indicators)",
        ]
      : ["yfinance (prices & fundamentals)", "FRED (macro indicators)"];

  return (
    <GlassPanel>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Database size={14} className="text-primary" />
            <h3 className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
              Transparency Layer
            </h3>
          </div>
          <p className="text-xs text-on-surface-variant">
            How the AI score is constructed and what data feeds it.
          </p>
        </div>

        {/* Data Sources */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-on-surface uppercase tracking-wide flex items-center gap-2">
            <Database size={12} className="text-secondary" /> Data Sources
          </h4>
          <div className="flex flex-wrap gap-2">
            {dataSources.map((src) => (
              <span
                key={src}
                className="text-xs px-2.5 py-1 rounded-full bg-surface-high text-on-surface-variant"
              >
                {src}
              </span>
            ))}
          </div>
        </div>

        {/* Score Breakdown */}
        <div className="space-y-3">
          <h4 className="text-xs font-semibold text-on-surface uppercase tracking-wide flex items-center gap-2">
            <BarChart3 size={12} className="text-secondary" /> Score Breakdown (Raw Percentiles)
          </h4>
          <ScoreBreakdownBars scores={score.sub_scores} />
        </div>

        {/* Agent Reasoning */}
        {report && report.agent_outputs.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-xs font-semibold text-on-surface uppercase tracking-wide flex items-center gap-2">
              <BrainCircuit size={12} className="text-secondary" /> Agent Reasoning
            </h4>
            <div className="space-y-2">
              {report.agent_outputs.map((o) => (
                <AgentReasonCard key={o.agent} output={o} />
              ))}
            </div>
          </div>
        )}
      </div>
    </GlassPanel>
  );
}

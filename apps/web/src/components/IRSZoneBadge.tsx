"use client";

import type { AnjaliScores } from "@/lib/types";
import Link from "next/link";

interface IRSZoneBadgeProps {
  anjali: AnjaliScores;
  ticker: string;
  market?: string;
  /** Compact mode: just IRS% + zone label (for cards). Full mode: IRS% + bars + breakdown */
  compact?: boolean;
}

function irsZone(pct: number | null | undefined): { label: string; color: string; bg: string } {
  if (pct == null) return { label: "N/A", color: "text-on-surface-variant", bg: "bg-surface-container" };
  if (pct >= 65) return { label: "INVESTMENT READY", color: "text-primary-fixed", bg: "bg-primary-fixed/15" };
  if (pct >= 45) return { label: "CAUTION", color: "text-amber-400", bg: "bg-amber-500/15" };
  return { label: "AVOID", color: "text-cyber-red", bg: "bg-red-500/15" };
}

function scoreBar(value: number | null, min: number, max: number, label: string, colorFn: (v: number) => string) {
  if (value == null) return null;
  const pct = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
  return (
    <div className="space-y-0.5">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono uppercase tracking-wider text-on-surface-variant">{label}</span>
        <span className={`text-xs font-bold font-mono ${colorFn(value)}`}>
          {value >= 0 ? "+" : ""}{value.toFixed(1)}
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-surface-container overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${value >= 0 ? "bg-primary-fixed" : "bg-cyber-red"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function gScoreColor(g: number): string {
  if (g >= 4) return "text-primary-fixed";
  if (g >= 0) return "text-on-surface";
  return "text-cyber-red";
}

function riskEffColor(r: number): string {
  if (r >= 2) return "text-primary-fixed";
  if (r >= 0) return "text-on-surface";
  return "text-cyber-red";
}

export default function IRSZoneBadge({ anjali, ticker, market = "US", compact = false }: IRSZoneBadgeProps) {
  const irsPct = anjali.irs_pct ?? null;
  const gScore = anjali.g_score ?? null;
  const riskEff = anjali.risk_eff_score ?? null;
  const zone = irsZone(irsPct);

  if (compact) {
    return (
      <div className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded ${zone.bg}`}>
        <span className={`font-headline text-sm font-bold ${zone.color}`}>
          {irsPct != null ? `${irsPct.toFixed(0)}%` : "—"}
        </span>
        <span className={`text-[9px] font-mono font-bold tracking-wider ${zone.color}`}>
          {zone.label}
        </span>
      </div>
    );
  }

  return (
    <div className="ghost-border bg-surface-low/40 rounded-xl p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-mono uppercase tracking-wider text-primary">
          Investment Readiness Score
        </h3>
        <Link
          href={`/stocks/${ticker}/anjali?market=${market}`}
          className="text-[10px] font-mono text-primary-fixed hover:underline"
        >
          Full Breakdown →
        </Link>
      </div>

      {/* IRS% Hero */}
      <div className={`flex items-baseline gap-3 px-4 py-3 rounded-lg ${zone.bg}`}>
        <span className={`font-headline text-4xl font-bold ${zone.color}`}>
          {irsPct != null ? `${irsPct.toFixed(0)}%` : "—"}
        </span>
        <span className={`text-sm font-mono font-bold tracking-wider ${zone.color}`}>
          {zone.label}
        </span>
      </div>

      {/* G Score bar */}
      {scoreBar(gScore, -12, 12, "G Score", gScoreColor)}

      {/* Risk Efficiency bar */}
      {scoreBar(riskEff, -8, 8, "Risk Efficiency", riskEffColor)}

      {/* Sub-scores grid */}
      <div className="grid grid-cols-4 gap-x-2 gap-y-1 pt-2 border-t border-outline-variant/20">
        {[
          { label: "Growth", value: anjali.growth_score },
          { label: "Return", value: anjali.return_score },
          { label: "Value", value: anjali.valuation_score },
          { label: "Risk", value: anjali.risk_score },
        ].map(({ label, value }) => (
          <div key={label}>
            <span className="text-[9px] text-on-surface-variant">{label}</span>
            <div className={`text-[11px] font-mono font-medium ${
              value != null
                ? value >= 1.5 ? "text-tertiary-fixed-dim" : value >= 0.5 ? "text-primary-fixed" : value < -0.5 ? "text-cyber-red" : "text-on-surface-variant"
                : "text-on-surface-variant"
            }`}>
              {value != null ? (value >= 0 ? "+" : "") + value.toFixed(1) : "—"}
            </div>
          </div>
        ))}
      </div>

      {/* Tags */}
      <div className="flex gap-1.5">
        {anjali.valuation_sweet_spot && (
          <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-tertiary/15 text-tertiary border border-tertiary/30">
            VALUE SWEET SPOT
          </span>
        )}
        {anjali.is_loss_making && (
          <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-error/15 text-error border border-error/30">
            LOSS-MAKING
          </span>
        )}
        {(gScore != null && gScore < -4) && (
          <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-red-500/15 text-red-400 border border-red-500/30">
            HARD SELL
          </span>
        )}
      </div>
    </div>
  );
}
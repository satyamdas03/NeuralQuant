"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { AnjaliDetailResponse, Market } from "@/lib/types";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import { ArrowLeft, Loader2, AlertTriangle } from "lucide-react";

function ScoreBar({ label, value, min, max, unit = "" }: { label: string; value: number | null; min: number; max: number; unit?: string }) {
  if (value == null) return null;
  const pct = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
  const isPositive = value >= 0;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono uppercase tracking-wider text-on-surface-variant">{label}</span>
        <span className={`text-sm font-bold font-mono ${isPositive ? "text-primary-fixed" : value < -0.5 ? "text-cyber-red" : "text-on-surface-variant"}`}>
          {value >= 0 ? "+" : ""}{value.toFixed(1)}{unit}
        </span>
      </div>
      <div className="h-2 rounded-full bg-surface-container overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${isPositive ? "bg-primary-fixed" : "bg-cyber-red"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function quintileLabel(score: number | null | undefined): string {
  if (score == null) return "—";
  if (score >= 1.5) return "Q5 ★";
  if (score >= 0.5) return "Q4";
  if (score >= -0.5) return "Q3";
  if (score >= -1.5) return "Q2";
  return "Q1";
}

function irsZone(pct: number): { label: string; color: string; bg: string } {
  if (pct >= 65) return { label: "INVESTMENT READY", color: "text-primary-fixed", bg: "bg-primary-fixed/15" };
  if (pct >= 45) return { label: "CAUTION", color: "text-amber-400", bg: "bg-amber-500/15" };
  return { label: "AVOID", color: "text-red-400", bg: "bg-red-500/15" };
}

export default function AnjaliDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const ticker = (params.ticker as string) ?? "";
  const market = (searchParams.get("market") ?? "IN") as Market;

  const [data, setData] = useState<AnjaliDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getAnjali(ticker, market)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load Anjali data"))
      .finally(() => setLoading(false));
  }, [ticker, market]);

  if (loading) {
    return (
      <div className="space-y-5 p-4 lg:p-6">
        <div className="flex items-center justify-center py-12 gap-2">
          <Loader2 size={24} className="animate-spin text-primary" />
          <span className="text-on-surface-variant">Loading Anjali analysis…</span>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-5 p-4 lg:p-6">
        <div className="text-center py-12">
          <AlertTriangle size={24} className="mx-auto text-error mb-2" />
          <p className="text-error">{error || "Anjali data not available for this stock."}</p>
          <p className="text-sm text-on-surface-variant mt-2">Try switching the market (IN/US) or check back later.</p>
        </div>
      </div>
    );
  }

  const zone = irsZone(data.irs_pct ?? 0);
  const isSell = data.sell_signal;

  return (
    <div className="space-y-5 p-4 lg:p-6 max-w-2xl mx-auto">
      {/* Back link */}
      <Link
        href={`/stocks/${ticker}?market=${market}`}
        className="inline-flex items-center gap-1.5 text-xs font-mono text-on-surface-variant hover:text-primary transition-colors"
      >
        <ArrowLeft size={14} />
        Back to {ticker.toUpperCase()}
      </Link>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-headline text-xl font-bold text-on-surface">
            {ticker.toUpperCase()} · Anjali Analysis
          </h1>
          {data.name && <p className="text-sm text-on-surface-variant">{data.name}</p>}
          {data.sector && <p className="text-xs text-on-surface-variant">{data.sector}</p>}
        </div>
        {data.index_group && (
          <span className="text-[10px] font-mono px-2 py-1 rounded bg-surface-container text-on-surface-variant">
            {data.index_group}
          </span>
        )}
      </div>

      {/* IRS% Hero */}
      {data.irs_pct != null && (
        <div className={`rounded-xl p-6 ${zone.bg} border border-outline-variant/30`}>
          <div className="text-center space-y-2">
            <span className="text-[10px] font-mono uppercase tracking-wider text-on-surface-variant">
              Investment Readiness Score
            </span>
            <div className={`font-headline text-6xl font-bold ${zone.color}`}>
              {data.irs_pct.toFixed(1)}%
            </div>
            <span className={`text-sm font-mono font-bold uppercase tracking-wider ${zone.color}`}>
              {zone.label}
            </span>
            {isSell && (
              <div className="flex items-center justify-center gap-1.5 mt-2">
                <AlertTriangle size={14} className="text-red-400" />
                <span className="text-xs font-mono text-red-400">{data.sell_reason}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* G Score Breakdown */}
      <GhostBorderCard>
        <div className="space-y-3">
          <h3 className="text-xs font-mono uppercase tracking-wider text-primary">G Score Breakdown</h3>
          <ScoreBar label="Growth" value={data.growth_score} min={-4} max={4} />
          <ScoreBar label="Return" value={data.return_score} min={-4} max={4} />
          <ScoreBar label="Valuation" value={data.valuation_score} min={-4} max={4} />
          <ScoreBar label="Total G Score" value={data.g_score} min={-12} max={12} />
          <div className="grid grid-cols-3 gap-x-4 gap-y-1 pt-2 border-t border-outline-variant/20">
            {[
              { label: "Growth", score: data.growth_score },
              { label: "Return", score: data.return_score },
              { label: "Value", score: data.valuation_score },
            ].map(({ label, score }) => (
              <div key={label} className="text-center">
                <span className="text-[9px] text-on-surface-variant">{label}</span>
                <div className={`text-sm font-mono font-bold ${
                  score != null
                    ? score >= 1.5 ? "text-tertiary-fixed-dim" : score >= 0.5 ? "text-primary-fixed" : score < -0.5 ? "text-cyber-red" : "text-on-surface-variant"
                    : "text-on-surface-variant"
                }`}>
                  {quintileLabel(score)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </GhostBorderCard>

      {/* Risk Efficiency Breakdown */}
      <GhostBorderCard>
        <div className="space-y-3">
          <h3 className="text-xs font-mono uppercase tracking-wider text-primary">Risk Efficiency</h3>
          <ScoreBar label="Risk Score (raw)" value={data.risk_score} min={-4} max={4} />
          <ScoreBar label="Risk Efficiency (×2)" value={data.risk_eff_score} min={-8} max={8} />
        </div>
      </GhostBorderCard>

      {/* Composite + Fundamentals */}
      <GhostBorderCard>
        <div className="space-y-2">
          <h3 className="text-xs font-mono uppercase tracking-wider text-primary">Composite & Fundamentals</h3>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2">
            <Metric label="Composite Score" value={data.composite != null ? `${data.composite >= 0 ? "+" : ""}${data.composite.toFixed(1)}/16` : "—"} />
            <Metric label="P/E Ratio" value={data.pe_ratio != null ? data.pe_ratio.toFixed(1) : "—"} />
            <Metric label="Market Cap" value={data.market_cap_bn != null ? `₹${data.market_cap_bn.toFixed(0)}B` : "—"} />
            <Metric label="DII Quarter" value={data.dii_quarter != null ? data.dii_quarter.toFixed(1) : "—"} />
            <Metric label="FII Quarter" value={data.fii_quarter != null ? data.fii_quarter.toFixed(1) : "—"} />
            <Metric label="IRS Raw" value={data.irs_raw != null ? `${data.irs_raw >= 0 ? "+" : ""}${data.irs_raw.toFixed(1)}` : "—"} />
          </div>
        </div>
      </GhostBorderCard>

      {/* Methodology */}
      <GhostBorderCard>
        <div className="space-y-2 text-xs text-on-surface-variant">
          <h3 className="text-xs font-mono uppercase tracking-wider text-primary">Methodology</h3>
          <p><strong>IRS%</strong> = ((G Score + Risk Efficiency Score + 20) / 40) × 100</p>
          <p><strong>G Score</strong> = Growth Score + Return Score + Valuation Score (range: -12 to +12)</p>
          <p><strong>Risk Efficiency Score</strong> = Risk Score × 2 (range: -8 to +8)</p>
          <p className="mt-1"><strong>Sell Signal:</strong> G Score &lt; -4 or Risk Score &lt; -3.5 → HARD SELL</p>
          <p><strong>Caution Zone:</strong> G Score &lt; -0.5 → NEUTRAL (not investment ready)</p>
        </div>
      </GhostBorderCard>

      {/* SEBI Disclaimer */}
      <p className="text-[9px] text-on-surface-variant text-center">
        {data.sebi_disclaimer || "This is AI-generated analysis, not SEBI-registered investment advice. Consult a certified financial advisor."}
      </p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-[10px] text-on-surface-variant uppercase tracking-wider">{label}</span>
      <div className="text-sm font-mono font-medium text-on-surface">{value}</div>
    </div>
  );
}
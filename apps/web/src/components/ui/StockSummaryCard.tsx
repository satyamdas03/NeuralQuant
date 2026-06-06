"use client";

import type { StockSummary, AnjaliScores } from "@/lib/types";

type Props = { summary: StockSummary };

function fmtNum(v: number | null, decimals = 2): string {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtMcap(v: number | null, cur: string): string {
  if (v === null || v === undefined) return "—";
  if (cur === "₹") {
    if (v >= 1e13) return `₹${(v / 1e13).toFixed(1)}L Cr`;
    if (v >= 1e11) return `₹${(v / 1e11).toFixed(1)}K Cr`;
    if (v >= 1e7) return `₹${(v / 1e7).toFixed(0)} Cr`;
    return `₹${fmtNum(v, 0)}`;
  }
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${fmtNum(v, 0)}`;
}

function anjaliCompositeLabel(c: number | null | undefined): string {
  if (c == null) return "—";
  return c >= 0 ? `+${c.toFixed(1)}` : c.toFixed(1);
}

function anjaliCompositeColor(c: number | null | undefined): string {
  if (c == null) return "text-on-surface-variant";
  if (c >= 6) return "text-tertiary-fixed-dim";
  if (c >= 2) return "text-primary-fixed";
  if (c >= -2) return "text-on-surface-variant";
  return "text-cyber-red";
}

function quintileLabel(score: number | null | undefined): string {
  if (score == null) return "—";
  // Scores range -4 to +4
  if (score >= 1.5) return "Q5 ★";
  if (score >= 0.5) return "Q4";
  if (score >= -0.5) return "Q3";
  if (score >= -1.5) return "Q2";
  return "Q1";
}

function quintileColor(score: number | null | undefined): string {
  if (score == null) return "text-on-surface-variant";
  if (score >= 1.5) return "text-tertiary-fixed-dim";
  if (score >= 0.5) return "text-primary-fixed";
  return "text-on-surface-variant";
}

function AnjaliRow({ anjali }: { anjali: AnjaliScores }) {
  const irsPct = anjali.irs_pct;
  const irsZone = irsPct == null ? null
    : irsPct >= 65 ? "INVESTMENT READY"
    : irsPct >= 45 ? "CAUTION"
    : "AVOID";
  const irsColor = irsPct == null ? ""
    : irsPct >= 65 ? "text-primary-fixed"
    : irsPct >= 45 ? "text-amber-400"
    : "text-red-400";

  return (
    <div className="mt-1.5 pt-1.5 border-t border-outline-variant/20">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] font-mono uppercase tracking-wider text-primary">
          QuantFactor Screener
        </span>
        <div className="flex items-center gap-2">
          {irsPct != null && (
            <span className={`text-xs font-bold font-mono ${irsColor}`}>
              IRS {irsPct.toFixed(0)}%
              <span className="text-[9px] ml-1">{irsZone}</span>
            </span>
          )}
          <span className={`text-xs font-bold font-mono ${anjaliCompositeColor(anjali.composite)}`}>
            {anjaliCompositeLabel(anjali.composite)}
            <span className="text-[10px] text-on-surface-variant">/16</span>
          </span>
        </div>
      </div>
      <div className="grid grid-cols-4 gap-x-2 gap-y-0.5">
        {[
          { label: "Growth", score: anjali.growth_score },
          { label: "Return", score: anjali.return_score },
          { label: "Value", score: anjali.valuation_score },
          { label: "Risk", score: anjali.risk_score },
        ].map(({ label, score }) => (
          <div key={label}>
            <span className="text-[9px] text-on-surface-variant">{label}</span>
            <div className={`text-[11px] font-mono font-medium ${quintileColor(score)}`}>
              {quintileLabel(score)}
            </div>
          </div>
        ))}
      </div>
      <div className="flex gap-1.5 mt-1">
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
        {anjali.g_score != null && anjali.g_score < -4 && (
          <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-red-500/15 text-red-400 border border-red-500/30">
            HARD SELL
          </span>
        )}
      </div>
    </div>
  );
}

export default function StockSummaryCard({ summary }: Props) {
  const cur = summary.currency || "$";
  const chg = summary.change_pct;
  const chgColor = chg !== null && chg !== undefined
    ? chg >= 0 ? "text-tertiary" : "text-error"
    : "text-on-surface-variant";

  const rows: { label: string; value: string; accent?: string }[] = [];

  if (summary.forecast_score !== null) {
    rows.push({ label: "ForeCast", value: `${summary.forecast_score}/10`, accent: summary.forecast_score >= 7 ? "text-tertiary" : summary.forecast_score >= 5 ? "text-secondary" : "text-error" });
  }
  if (summary.pe_ttm !== null) {
    rows.push({ label: "P/E (TTM)", value: fmtNum(summary.pe_ttm, 1) });
  }
  if (summary.eps_ttm !== null) {
    rows.push({ label: "EPS (TTM)", value: `${cur}${fmtNum(summary.eps_ttm, 2)}` });
  }
  if (summary.pb_ratio !== null) {
    rows.push({ label: "P/B", value: fmtNum(summary.pb_ratio, 2) });
  }
  if (summary.market_cap !== null) {
    rows.push({ label: "Market Cap", value: fmtMcap(summary.market_cap, cur) });
  }
  if (summary.week_52_low !== null && summary.week_52_high !== null) {
    rows.push({ label: "52-Week Range", value: `${cur}${fmtNum(summary.week_52_low, 0)} – ${cur}${fmtNum(summary.week_52_high, 0)}` });
  }
  if (summary.analyst_target !== null) {
    rows.push({ label: "Analyst Target", value: `${cur}${fmtNum(summary.analyst_target, 0)}` });
  }
  if (summary.beta !== null) {
    rows.push({ label: "Beta", value: fmtNum(summary.beta, 2) });
  }
  if (summary.sector) {
    rows.push({ label: "Sector", value: summary.sector });
  }
  // OpenBB-enriched fields (shown if available)
  if (summary.analyst_consensus) {
    const ac = summary.analyst_consensus;
    const acColor = ac.includes("buy") || ac.includes("outperform") ? "text-tertiary" : ac.includes("sell") || ac.includes("underperform") ? "text-error" : "text-secondary";
    rows.push({ label: "Consensus", value: ac.replace(/_/g, " ").toUpperCase(), accent: acColor });
  }
  if (summary.analyst_buy_pct != null) {
    rows.push({ label: "Buy Rating", value: `${summary.analyst_buy_pct}%`, accent: summary.analyst_buy_pct >= 70 ? "text-tertiary" : undefined });
  }
  if (summary.altman_z_score != null) {
    rows.push({ label: "Altman Z", value: `${summary.altman_z_score}` });
  }
  if (summary.piotroski_score != null) {
    rows.push({ label: "Piotroski", value: `${summary.piotroski_score}/9` });
  }
  if (summary.iv_percentile != null) {
    rows.push({ label: "IV %ile", value: `${summary.iv_percentile.toFixed(0)}%` });
  }
  if (summary.put_call_ratio != null) {
    rows.push({ label: "Put/Call", value: `${summary.put_call_ratio.toFixed(2)}` });
  }

  return (
    <div className="rounded-lg bg-surface-high/50 border border-outline-variant/30 overflow-hidden">
      <div className="flex items-baseline justify-between px-3 pt-2.5 pb-1.5 border-b border-outline-variant/20">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-on-surface">{summary.ticker}</span>
          {summary.name && (
            <span className="text-xs text-on-surface-variant truncate max-w-[180px]">{summary.name}</span>
          )}
        </div>
        <div className="flex items-baseline gap-2">
          {summary.price !== null && (
            <span className="text-sm font-semibold text-on-surface tabular-nums">
              {cur}{fmtNum(summary.price)}
            </span>
          )}
          {chg !== null && (
            <span className={`text-xs font-medium tabular-nums ${chgColor}`}>
              {chg >= 0 ? "+" : ""}{chg.toFixed(2)}%
            </span>
          )}
        </div>
      </div>
      {rows.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-1.5 px-3 py-2">
          {rows.map((r, i) => (
            <div key={i}>
              <span className="text-[10px] text-on-surface-variant uppercase tracking-wider">{r.label}</span>
              <div className={`text-xs font-medium tabular-nums ${r.accent || "text-on-surface"}`}>{r.value}</div>
            </div>
          ))}
        </div>
      )}
      {summary.anjali && <AnjaliRow anjali={summary.anjali} />}
    </div>
  );
}
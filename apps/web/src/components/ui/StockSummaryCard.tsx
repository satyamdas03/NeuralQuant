"use client";

import type { StockSummary } from "@/lib/types";

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
    </div>
  );
}
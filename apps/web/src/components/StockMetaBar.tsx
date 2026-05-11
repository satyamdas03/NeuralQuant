"use client";
import type { StockMeta } from "@/lib/types";
import GhostBorderCard from "@/components/ui/GhostBorderCard";

const REC_COLORS: Record<string, string> = {
  "strong_buy": "text-tertiary",
  "buy":        "text-tertiary",
  "hold":       "text-secondary",
  "underperform": "text-error",
  "sell":       "text-error",
  "strong_sell": "text-error",
};

function MetaItem({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[10px] font-medium text-on-surface-variant uppercase tracking-widest">{label}</div>
      <div className={`text-sm font-semibold mt-0.5 truncate ${color || "text-on-surface"}`}>{value}</div>
    </div>
  );
}

export function StockMetaBar({ meta, market = "US" }: { meta: StockMeta; market?: string }) {
  const rec = meta.analyst_recommendation?.toLowerCase() ?? "";
  const recColor = REC_COLORS[rec] ?? "text-on-surface";
  const recLabel = rec.replace(/_/g, " ").toUpperCase() || "—";
  const cur = market === "IN" ? "₹" : "$";

  const items = [
    { label: "Market Cap",   value: meta.market_cap_fmt ?? "—" },
    { label: "P/E (TTM)",    value: meta.pe_ttm ? `${meta.pe_ttm}×` : "—" },
    { label: "P/B",          value: meta.pb_ratio ? `${meta.pb_ratio}×` : "—" },
    { label: "Beta",         value: meta.beta ? meta.beta.toFixed(2) : "—" },
    {
      label: "52W Range",
      value: meta.week_52_low && meta.week_52_high
        ? `${cur}${Number(meta.week_52_low).toFixed(0)} – ${cur}${Number(meta.week_52_high).toFixed(0)}`
        : "—",
    },
    { label: "Next Earnings", value: meta.earnings_date ?? "—" },
    { label: "Analyst Target", value: meta.analyst_target ? `${cur}${Number(meta.analyst_target).toFixed(0)}` : "—" },
    { label: "Consensus",    value: recLabel, color: recColor },
    { label: "Sector",       value: meta.sector ?? "—" },
    { label: "Dividend",     value: meta.dividend_yield ? `${meta.dividend_yield}%` : "—" },
  ];

  // Extra OpenBB-enriched fields (shown if available)
  const extraItems: { label: string; value: string; color?: string }[] = [];
  if (meta.analyst_consensus) {
    const ac = meta.analyst_consensus;
    const acColor = REC_COLORS[ac.toLowerCase()] ?? "text-on-surface";
    extraItems.push({ label: "Analyst Consensus", value: ac.replace(/_/g, " ").toUpperCase(), color: acColor });
  }
  if (meta.analyst_count) {
    extraItems.push({ label: "Analysts", value: `${meta.analyst_count}` });
  }
  if (meta.altman_z_score) {
    extraItems.push({ label: "Altman Z", value: `${meta.altman_z_score}` });
  }
  if (meta.piotroski_score) {
    extraItems.push({ label: "Piotroski", value: `${meta.piotroski_score}/9` });
  }
  if (meta.yield_curve_spread != null) {
    extraItems.push({ label: "2y/10y Spread", value: `${meta.yield_curve_spread}bps` });
  }
  if (meta.yield_curve_10y != null) {
    extraItems.push({ label: "US 10Y", value: `${meta.yield_curve_10y}%` });
  }

  return (
    <GhostBorderCard>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-x-6 gap-y-3">
        {items.map(({ label, value, color }) => (
          <MetaItem key={label} label={label} value={value} color={color} />
        ))}
        {extraItems.map(({ label, value, color }) => (
          <MetaItem key={label} label={label} value={value} color={color} />
        ))}
      </div>
    </GhostBorderCard>
  );
}
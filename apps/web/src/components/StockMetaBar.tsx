"use client";
import type { StockMeta } from "@/lib/types";

const REC_COLORS: Record<string, string> = {
  "strong_buy": "text-emerald-400",
  "buy":        "text-emerald-400",
  "hold":       "text-yellow-400",
  "underperform": "text-red-400",
  "sell":       "text-red-400",
  "strong_sell": "text-red-400",
};

function MetaItem({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[10px] font-medium text-gray-500 uppercase tracking-widest">{label}</div>
      <div className={`text-sm font-semibold mt-0.5 truncate ${color || "text-gray-100"}`}>{value}</div>
    </div>
  );
}

export function StockMetaBar({ meta }: { meta: StockMeta }) {
  const rec = meta.analyst_recommendation?.toLowerCase() ?? "";
  const recColor = REC_COLORS[rec] ?? "text-gray-300";
  const recLabel = rec.replace(/_/g, " ").toUpperCase() || "—";

  const items = [
    { label: "Market Cap",   value: meta.market_cap_fmt ?? "—" },
    { label: "P/E (TTM)",    value: meta.pe_ttm ? `${meta.pe_ttm}×` : "—" },
    { label: "P/B",          value: meta.pb_ratio ? `${meta.pb_ratio}×` : "—" },
    { label: "Beta",         value: meta.beta ? meta.beta.toFixed(2) : "—" },
    {
      label: "52W Range",
      value: meta.week_52_low && meta.week_52_high
        ? `$${Number(meta.week_52_low).toFixed(0)} – $${Number(meta.week_52_high).toFixed(0)}`
        : "—",
    },
    { label: "Next Earnings", value: meta.earnings_date ?? "—" },
    { label: "Analyst Target", value: meta.analyst_target ? `$${Number(meta.analyst_target).toFixed(0)}` : "—" },
    { label: "Consensus",    value: recLabel, color: recColor },
    { label: "Sector",       value: meta.sector ?? "—" },
    { label: "Dividend",     value: meta.dividend_yield ? `${meta.dividend_yield}%` : "—" },
  ];

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-x-6 gap-y-3">
        {items.map(({ label, value, color }) => (
          <MetaItem key={label} label={label} value={value} color={color} />
        ))}
      </div>
    </div>
  );
}

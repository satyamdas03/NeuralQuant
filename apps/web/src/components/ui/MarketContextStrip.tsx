"use client";

import type { MarketContextCard } from "@/lib/types";

export default function MarketContextStrip({
  cards,
}: {
  cards: MarketContextCard[];
}) {
  if (!cards || cards.length === 0) {
    return (
      <div className="rounded-lg bg-surface-high px-3 py-2 text-xs text-on-surface-variant">
        Market data unavailable
      </div>
    );
  }

  return (
    <div className="flex gap-2 overflow-x-auto pb-1">
      {cards.map((c, i) => (
        <div
          key={i}
          className="flex-shrink-0 rounded-lg bg-surface-high border border-outline/30 px-3 py-2 min-w-[100px]"
        >
          <div className="text-[10px] text-on-surface-variant uppercase tracking-wide">{c.label}</div>
          <div className="text-sm font-semibold text-on-surface">{c.value}</div>
          {c.change && (
            <div className={`text-[10px] ${c.change.startsWith("+") ? "text-green-400" : c.change.startsWith("-") ? "text-red-400" : "text-on-surface-variant"}`}>
              {c.change}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

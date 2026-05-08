"use client";

import type { PortfolioStockCard as PSC } from "@/lib/types";

export default function PortfolioStockCard({ stock }: { stock: PSC }) {
  return (
    <div className="rounded-xl bg-surface-high border border-outline/30 p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-on-surface">{stock.ticker}</span>
          {stock.name && <span className="text-xs text-on-surface-variant">{stock.name}</span>}
        </div>
        <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
          {stock.allocation_pct}%
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2 text-center">
        {stock.entry_price && (
          <div className="rounded bg-surface-container px-2 py-1">
            <div className="text-[10px] text-on-surface-variant">Entry</div>
            <div className="text-xs font-medium text-on-surface">{stock.entry_price}</div>
          </div>
        )}
        {stock.target_price && (
          <div className="rounded bg-surface-container px-2 py-1">
            <div className="text-[10px] text-on-surface-variant">Target</div>
            <div className="text-xs font-medium text-green-400">{stock.target_price}</div>
          </div>
        )}
        {stock.stop_loss && (
          <div className="rounded bg-surface-container px-2 py-1">
            <div className="text-[10px] text-on-surface-variant">Stop Loss</div>
            <div className="text-xs font-medium text-red-400">{stock.stop_loss}</div>
          </div>
        )}
      </div>

      {stock.risk_reward && (
        <div className="text-[10px] text-on-surface-variant">
          R:R {stock.risk_reward}
        </div>
      )}
      {stock.rationale && (
        <p className="text-xs text-on-surface leading-snug">{stock.rationale}</p>
      )}
      {stock.confidence && (
        <div className="text-[10px] text-on-surface-variant">
          ForeCast: {stock.confidence}/10
        </div>
      )}
    </div>
  );
}

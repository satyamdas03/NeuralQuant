"use client";

import type { TradeSignal } from "@/lib/types";
import GlassPanel from "@/components/ui/GlassPanel";
import { TrendingUp, TrendingDown, DollarSign, Target, AlertTriangle } from "lucide-react";

function formatMarketCap(mcap: number | null): string {
  if (!mcap) return "—";
  if (mcap >= 1e12) return `$${(mcap / 1e12).toFixed(2)}T`;
  if (mcap >= 1e9) return `$${(mcap / 1e9).toFixed(1)}B`;
  if (mcap >= 1e6) return `$${(mcap / 1e6).toFixed(0)}M`;
  return `$${mcap.toFixed(0)}`;
}

function EdgeBadge({ edge }: { edge: number }) {
  const colors =
    edge >= 0.3
      ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
      : edge >= 0.15
        ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
        : "bg-sky-500/15 text-sky-400 border-sky-500/30";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${colors}`}>
      <TrendingUp size={12} />
      {(edge * 100).toFixed(1)}% edge
    </span>
  );
}

export default function SignalFeed({ signals, loading }: { signals: TradeSignal[]; loading: boolean }) {
  if (loading) {
    return (
      <GlassPanel>
        <div className="space-y-3 animate-pulse">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-16 rounded-xl bg-surface-high" />
          ))}
        </div>
      </GlassPanel>
    );
  }

  if (!signals.length) {
    return (
      <GlassPanel>
        <div className="py-8 text-center text-sm text-on-surface-variant">
          <AlertTriangle size={32} className="mx-auto mb-2 opacity-40" />
          <p>No actionable signals found.</p>
          <p className="mt-1 text-xs">Try lowering the edge threshold or switching strategies.</p>
        </div>
      </GlassPanel>
    );
  }

  return (
    <div className="space-y-2">
      {signals.map((s, i) => (
        <GlassPanel key={`${s.ticker}-${i}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xs font-mono text-on-surface-variant w-5">{i + 1}</span>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm">{s.ticker}</span>
                  <span className="text-[10px] uppercase text-on-surface-variant bg-surface-high px-1.5 py-0.5 rounded">
                    {s.market}
                  </span>
                  {s.sector && (
                    <span className="text-[10px] text-on-surface-variant truncate max-w-[100px]">
                      {s.sector}
                    </span>
                  )}
                </div>
                <div className="mt-1 flex items-center gap-3 text-[11px] text-on-surface-variant">
                  {s.current_price && <span>${s.current_price.toFixed(2)}</span>}
                  {s.pe_ttm && <span>P/E {s.pe_ttm.toFixed(1)}x</span>}
                  <span>{formatMarketCap(s.market_cap)}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="text-right">
                <EdgeBadge edge={s.edge} />
                <div className="mt-1 flex items-center justify-end gap-1 text-xs text-on-surface-variant">
                  <span className="text-[10px]">score</span>
                  <span className="font-mono font-medium text-on-surface">
                    {(s.composite_score * 100).toFixed(0)}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-1 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5">
                <DollarSign size={14} className="text-emerald-400" />
                <span className="font-mono text-sm font-bold text-emerald-300">
                  ${s.bet.toFixed(0)}
                </span>
                {s.capped && (
                  <span className="text-[9px] text-amber-400" title="Capped at max bet">
                    cap
                  </span>
                )}
              </div>

              {s.analyst_target && s.current_price && (
                <div className="hidden sm:flex flex-col items-end text-[10px]">
                  <div className="flex items-center gap-1 text-on-surface-variant">
                    <Target size={10} />
                    <span>target ${s.analyst_target.toFixed(2)}</span>
                  </div>
                  <span className="text-emerald-400">
                    +{(((s.analyst_target - s.current_price) / s.current_price) * 100).toFixed(1)}%
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Progress bar: composite_score */}
          <div className="mt-2 h-1 rounded-full bg-surface-high overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-sky-500 to-emerald-400 transition-all"
              style={{ width: `${Math.min(s.composite_score * 100, 100)}%` }}
            />
          </div>
        </GlassPanel>
      ))}
    </div>
  );
}

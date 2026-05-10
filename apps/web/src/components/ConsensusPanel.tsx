"use client";

import { useState } from "react";
import type { OptionsSnapshot, StockMeta, Market } from "@/lib/types";
import { api } from "@/lib/api";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import { BarChart3, ChevronDown, ChevronUp } from "lucide-react";

function fmtNum(v: number | null, decimals = 2): string {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function fmtBigNum(v: number | null): string {
  if (v === null || v === undefined) return "—";
  if (v >= 1e12) return `${(v / 1e12).toFixed(1)}T`;
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return v.toFixed(0);
}

const CONSENSUS_COLORS: Record<string, string> = {
  strong_buy: "bg-tertiary text-on-primary",
  buy: "bg-tertiary/80 text-on-primary",
  outperform: "bg-tertiary/60 text-on-primary",
  hold: "bg-secondary/20 text-on-surface",
  neutral: "bg-secondary/20 text-on-surface",
  underperform: "bg-error/20 text-error",
  sell: "bg-error text-on-primary",
  strong_sell: "bg-error text-on-primary",
};

function ConsensusBadge({ consensus }: { consensus: string | null }) {
  if (!consensus) return <span className="text-on-surface-variant">—</span>;
  const key = consensus.toLowerCase().replace(/\s+/g, "_");
  const color = CONSENSUS_COLORS[key] || "bg-surface-high text-on-surface";
  const label = consensus.replace(/_/g, " ").toUpperCase();
  return (
    <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-bold uppercase ${color}`}>
      {label}
    </span>
  );
}

function RatingBar({ buy, hold, sell }: { buy: number | null; hold: number | null; sell: number | null }) {
  const b = buy ?? 0;
  const h = hold ?? 0;
  const s = sell ?? 0;
  const total = b + h + s;
  if (total === 0) return null;
  const buyPct = (b / total) * 100;
  const holdPct = (h / total) * 100;
  const sellPct = (s / total) * 100;
  return (
    <div className="flex h-2 rounded-full overflow-hidden bg-surface-container mt-1">
      {buyPct > 0 && <div className="bg-tertiary" style={{ width: `${buyPct}%` }} title={`${b} Buy`} />}
      {holdPct > 0 && <div className="bg-secondary" style={{ width: `${holdPct}%` }} title={`${h} Hold`} />}
      {sellPct > 0 && <div className="bg-error" style={{ width: `${sellPct}%` }} title={`${s} Sell`} />}
    </div>
  );
}

export default function ConsensusPanel({ ticker, market = "US", meta }: { ticker: string; market?: Market; meta?: StockMeta | null }) {
  const [optionsData, setOptionsData] = useState<OptionsSnapshot | null>(null);
  const [expanded, setExpanded] = useState(false);

  // Try fetching richer options/ownership data (may fail if OpenBB disabled)
  useState(() => {
    api.getOptionsSnapshot(ticker, market)
      .then(setOptionsData)
      .catch(() => setOptionsData(null));
  });

  // Determine consensus from meta (always available) or options (richer)
  const metaConsensus = meta?.analyst_consensus;
  const metaAnalystCount = meta?.analyst_count;
  const metaAnalystTarget = meta?.analyst_target;

  const optConsensus = optionsData?.data?.consensus;
  const optOwnership = optionsData?.data?.ownership;

  // Nothing to show at all?
  const hasMetaConsensus = !!metaConsensus;
  const hasOptData = !!(optConsensus || optOwnership);
  if (!hasMetaConsensus && !hasOptData) return null;

  // Merge: prefer options data for detailed fields, fall back to meta
  const consensus = optConsensus ?? null;
  const cur = market === "IN" ? "₹" : "$";

  return (
    <GhostBorderCard>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between"
      >
        <div className="flex items-center gap-2">
          <BarChart3 size={14} className="text-primary" />
          <span className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
            Analyst Consensus & Ownership
          </span>
        </div>
        {expanded ? <ChevronUp size={16} className="text-on-surface-variant" /> : <ChevronDown size={16} className="text-on-surface-variant" />}
      </button>

      {expanded && (
        <div className="mt-3 space-y-4">
          {/* Consensus from meta (always shown if available) */}
          {hasMetaConsensus && (
            <div>
              <div className="flex items-center gap-3 mb-2">
                <ConsensusBadge consensus={metaConsensus} />
                {metaAnalystCount && (
                  <span className="text-xs text-on-surface-variant">{metaAnalystCount} analysts</span>
                )}
              </div>
              {metaAnalystTarget !== null && metaAnalystTarget !== undefined && (
                <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                  <div>
                    <span className="text-[10px] text-on-surface-variant uppercase">Analyst Target</span>
                    <div className="text-sm font-medium text-on-surface">{cur}{fmtNum(metaAnalystTarget, 0)}</div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Richer data from /options endpoint (if available) */}
          {consensus && (
            <div>
              <div className="flex items-center gap-3 mb-2">
                <ConsensusBadge consensus={consensus.consensus} />
                {consensus.analyst_count !== null && (
                  <span className="text-xs text-on-surface-variant">{consensus.analyst_count} analysts</span>
                )}
              </div>

              <RatingBar
                buy={consensus.buy_count}
                hold={consensus.hold_count}
                sell={consensus.sell_count}
              />

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-2 mt-3">
                {consensus.target_consensus !== null && (
                  <div>
                    <span className="text-[10px] text-on-surface-variant uppercase">Avg Target</span>
                    <div className="text-sm font-medium text-on-surface">{cur}{fmtNum(consensus.target_consensus, 0)}</div>
                  </div>
                )}
                {consensus.target_median !== null && (
                  <div>
                    <span className="text-[10px] text-on-surface-variant uppercase">Median Target</span>
                    <div className="text-sm font-medium text-on-surface">{cur}{fmtNum(consensus.target_median, 0)}</div>
                  </div>
                )}
                {consensus.target_high !== null && (
                  <div>
                    <span className="text-[10px] text-on-surface-variant uppercase">High Target</span>
                    <div className="text-sm font-medium text-tertiary">{cur}{fmtNum(consensus.target_high, 0)}</div>
                  </div>
                )}
                {consensus.target_low !== null && (
                  <div>
                    <span className="text-[10px] text-on-surface-variant uppercase">Low Target</span>
                    <div className="text-sm font-medium text-error">{cur}{fmtNum(consensus.target_low, 0)}</div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Ownership Section */}
          {optOwnership && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
                  Share Statistics
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-2">
                {optOwnership.outstanding_shares !== null && (
                  <div>
                    <span className="text-[10px] text-on-surface-variant uppercase">Shares Outstanding</span>
                    <div className="text-sm font-medium text-on-surface">{fmtBigNum(optOwnership.outstanding_shares)}</div>
                  </div>
                )}
                {optOwnership.float_shares !== null && (
                  <div>
                    <span className="text-[10px] text-on-surface-variant uppercase">Float</span>
                    <div className="text-sm font-medium text-on-surface">{fmtBigNum(optOwnership.float_shares)}</div>
                  </div>
                )}
                {optOwnership.short_interest !== null && (
                  <div>
                    <span className="text-[10px] text-on-surface-variant uppercase">Short Interest</span>
                    <div className="text-sm font-medium text-on-surface">{fmtBigNum(optOwnership.short_interest)}</div>
                  </div>
                )}
                {optOwnership.short_ratio !== null && (
                  <div>
                    <span className="text-[10px] text-on-surface-variant uppercase">Short Ratio</span>
                    <div className="text-sm font-medium text-on-surface">{fmtNum(optOwnership.short_ratio)}</div>
                  </div>
                )}
                {optOwnership.institutional_ownership_pct !== null && (
                  <div>
                    <span className="text-[10px] text-on-surface-variant uppercase">Institutional</span>
                    <div className="text-sm font-medium text-on-surface">{optOwnership.institutional_ownership_pct.toFixed(1)}%</div>
                  </div>
                )}
                {optOwnership.insider_ownership_pct !== null && (
                  <div>
                    <span className="text-[10px] text-on-surface-variant uppercase">Insider</span>
                    <div className="text-sm font-medium text-on-surface">{optOwnership.insider_ownership_pct.toFixed(1)}%</div>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="text-[10px] text-on-surface-variant pt-1 border-t border-outline/20">
            Data from OpenBB · Analyst estimates are not guarantees of future performance
          </div>
        </div>
      )}
    </GhostBorderCard>
  );
}
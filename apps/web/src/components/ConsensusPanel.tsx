"use client";

import { useEffect, useState } from "react";
import type { OptionsSnapshot, AnalystConsensus, ShareOwnership } from "@/lib/types";
import { api } from "@/lib/api";
import type { Market } from "@/lib/types";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import { TrendingUp, Users, BarChart3, ChevronDown, ChevronUp } from "lucide-react";

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

export default function ConsensusPanel({ ticker, market = "US" }: { ticker: string; market?: Market }) {
  const [data, setData] = useState<OptionsSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.getOptionsSnapshot(ticker, market)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [ticker, market]);

  if (loading) {
    return (
      <GhostBorderCard>
        <div className="flex items-center justify-center py-4">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <span className="ml-2 text-xs text-on-surface-variant">Loading analyst data…</span>
        </div>
      </GhostBorderCard>
    );
  }

  if (!data || !data.enabled) return null;

  const consensus = data.data?.consensus;
  const ownership = data.data?.ownership;

  if (!consensus && !ownership) return null;

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
          {/* Consensus Section */}
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
          {ownership && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Users size={14} className="text-secondary" />
                <span className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
                  Share Statistics
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-2">
                {ownership.outstanding_shares !== null && (
                  <div>
                    <span className="text-[10px] text-on-surface-variant uppercase">Shares Outstanding</span>
                    <div className="text-sm font-medium text-on-surface">{fmtBigNum(ownership.outstanding_shares)}</div>
                  </div>
                )}
                {ownership.float_shares !== null && (
                  <div>
                    <span className="text-[10px] text-on-surface-variant uppercase">Float</span>
                    <div className="text-sm font-medium text-on-surface">{fmtBigNum(ownership.float_shares)}</div>
                  </div>
                )}
                {ownership.short_interest !== null && (
                  <div>
                    <span className="text-[10px] text-on-surface-variant uppercase">Short Interest</span>
                    <div className="text-sm font-medium text-on-surface">{fmtBigNum(ownership.short_interest)}</div>
                  </div>
                )}
                {ownership.short_ratio !== null && (
                  <div>
                    <span className="text-[10px] text-on-surface-variant uppercase">Short Ratio</span>
                    <div className="text-sm font-medium text-on-surface">{fmtNum(ownership.short_ratio)}</div>
                  </div>
                )}
                {ownership.institutional_ownership_pct !== null && (
                  <div>
                    <span className="text-[10px] text-on-surface-variant uppercase">Institutional</span>
                    <div className="text-sm font-medium text-on-surface">{ownership.institutional_ownership_pct.toFixed(1)}%</div>
                  </div>
                )}
                {ownership.insider_ownership_pct !== null && (
                  <div>
                    <span className="text-[10px] text-on-surface-variant uppercase">Insider</span>
                    <div className="text-sm font-medium text-on-surface">{ownership.insider_ownership_pct.toFixed(1)}%</div>
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
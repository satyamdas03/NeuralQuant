"use client";

import { useEffect, useState } from "react";
import { guestBacktest } from "@/lib/api";
import type { AccuracyResponse } from "@/lib/types";
import GlassPanel from "@/components/ui/GlassPanel";
import MetricCard from "@/components/ui/MetricCard";
import GradientButton from "@/components/ui/GradientButton";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import { BarChart3, TrendingUp, Shield, Target } from "lucide-react";

export const dynamic = "force-dynamic";

export default function PerformancePage() {
  const [data, setData] = useState<AccuracyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const result = await guestBacktest.accuracy();
        setData(result);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load accuracy data");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-3">
          <div className="animate-spin w-8 h-8 border-2 border-primary border-t-transparent rounded-full mx-auto" />
          <p className="text-sm text-on-surface-variant">Loading walk-forward validation data...</p>
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-4 max-w-md">
          <p className="text-sm text-error">{error}</p>
          <GradientButton onClick={() => window.location.reload()} size="md">Retry</GradientButton>
        </div>
      </div>
    );
  }

  const hasData = data && data.observation_count > 0 && !data.is_fallback;

  return (
    <div className="space-y-6 p-4 lg:p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-3">
        <BarChart3 size={24} className="text-primary" />
        <div>
          <h1 className="font-headline text-xl font-bold text-on-surface">Performance & Accuracy</h1>
          <p className="text-xs text-on-surface-variant">
            Walk-forward validation results — NeuralQuant ForeCast vs market
          </p>
        </div>
      </div>

      {hasData ? (
        <>
          {/* Key metrics row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard
              label="Hit Rate (7+)"
              value={`${data.hit_rate_at_7plus}%`}
              accent="tertiary"
            />
            <MetricCard
              label="Hit Rate (5+)"
              value={`${data.hit_rate_at_5plus}%`}
              accent="tertiary"
            />
            <MetricCard
              label="Baseline"
              value={`${data.baseline_hit_rate}%`}
              accent="secondary"
            />
            <MetricCard
              label="Top-Bottom Spread"
              value={`${data.top_minus_bottom_spread > 0 ? "+" : ""}${data.top_minus_bottom_spread}%`}
              accent={data.top_minus_bottom_spread > 0 ? "tertiary" : "error"}
            />
          </div>

          {/* Detailed stats */}
          <GlassPanel>
            <h2 className="font-headline text-sm font-semibold text-on-surface uppercase tracking-wide mb-4">
              Detailed Metrics
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <StatRow icon={<TrendingUp size={16} />} label="Mean Return — Top Decile" value={`${data.mean_return_top_decile > 0 ? "+" : ""}${data.mean_return_top_decile}%`} positive={data.mean_return_top_decile > 0} />
              <StatRow icon={<TrendingUp size={16} />} label="Mean Return — Bottom Decile" value={`${data.mean_return_bottom_decile > 0 ? "+" : ""}${data.mean_return_bottom_decile}%`} positive={data.mean_return_bottom_decile > 0} />
              <StatRow icon={<Shield size={16} />} label="Sharpe — Top Quartile" value={data.sharpe_top_quartile.toFixed(2)} positive={data.sharpe_top_quartile > 0} />
              <StatRow icon={<Target size={16} />} label="Win Rate — Top Quartile" value={`${data.win_rate_top_quartile}%`} positive={data.win_rate_top_quartile > 50} />
              <StatRow icon={<Shield size={16} />} label="Max Drawdown — Top Quartile" value={`${data.max_drawdown_top_quartile}%`} positive={false} />
            </div>
          </GlassPanel>

          {/* Validation details */}
          <GlassPanel>
            <h2 className="font-headline text-sm font-semibold text-on-surface uppercase tracking-wide mb-3">
              Validation Details
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
              <Detail label="Observations" value={data.observation_count.toLocaleString()} />
              <Detail label="Period" value={data.period_start && data.period_end ? `${data.period_start} — ${data.period_end}` : "—"} />
              <Detail label="Avg Stocks/Period" value={data.avg_stocks_per_period.toFixed(1)} />
            </div>
            {data.note && (
              <p className="mt-3 text-xs text-on-surface-variant">{data.note}</p>
            )}
          </GlassPanel>

          {/* Methodology */}
          <GhostBorderCard className="p-4">
            <h2 className="font-headline text-sm font-semibold text-on-surface mb-2">Methodology</h2>
            <p className="text-xs text-on-surface-variant leading-relaxed">{data.methodology}</p>
            <p className="mt-2 text-xs text-on-surface-variant">{data.comparison}</p>
          </GhostBorderCard>
        </>
      ) : (
        <GhostBorderCard className="p-6 text-center">
          <p className="text-sm text-on-surface-variant">
            {data?.note || "Walk-forward validation data is being refreshed. Check back shortly."}
          </p>
        </GhostBorderCard>
      )}
    </div>
  );
}

function StatRow({ icon, label, value, positive }: { icon: React.ReactNode; label: string; value: string; positive: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <span className={positive ? "text-tertiary" : "text-error"}>{icon}</span>
      <div>
        <p className="text-xs text-on-surface-variant">{label}</p>
        <p className={`text-sm font-medium tabular-nums ${positive ? "text-tertiary" : "text-error"}`}>{value}</p>
      </div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] text-on-surface-variant uppercase tracking-wider">{label}</p>
      <p className="text-sm font-medium text-on-surface tabular-nums">{value}</p>
    </div>
  );
}
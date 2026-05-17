"use client";

import type { CalibrationReport } from "@/lib/types";
import GlassPanel from "@/components/ui/GlassPanel";
import { Target, TrendingUp, TrendingDown, BarChart3, Shield } from "lucide-react";

export default function RiskDashboard({
  calibration,
  loading,
}: {
  calibration: CalibrationReport | null;
  loading: boolean;
}) {
  return (
    <GlassPanel>
      <h3 className="text-sm font-semibold text-on-surface flex items-center gap-2 mb-3">
        <Shield size={16} className="text-primary" />
        Risk Dashboard
      </h3>

      {loading ? (
        <div className="space-y-3 animate-pulse">
          <div className="h-8 bg-surface-high" />
          <div className="h-8 bg-surface-high" />
          <div className="h-8 bg-surface-high" />
        </div>
      ) : calibration && calibration.n_trades > 0 ? (
        <div className="space-y-3">
          {/* Hit rate */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-on-surface-variant flex items-center gap-1">
              <Target size={12} /> Hit Rate
            </span>
            <span className="text-sm font-mono font-semibold text-on-surface">
              {(calibration.hit_rate * 100).toFixed(0)}%
            </span>
          </div>

          {/* Win/Loss */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-on-surface-variant flex items-center gap-1">
              <BarChart3 size={12} /> W / L
            </span>
            <span className="text-sm font-mono">
              <span className="text-emerald-400">{calibration.n_winners}</span>
              <span className="text-on-surface-variant"> / </span>
              <span className="text-rose-400">{calibration.n_losers}</span>
            </span>
          </div>

          {/* Avg PnL */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-on-surface-variant flex items-center gap-1">
              <TrendingUp size={12} /> Avg PnL
            </span>
            <span
              className={`text-sm font-mono font-semibold ${calibration.avg_pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}
            >
              {calibration.avg_pnl >= 0 ? "+" : ""}${calibration.avg_pnl.toFixed(2)}
            </span>
          </div>

          {/* Sharpe */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-on-surface-variant">Sharpe</span>
            <span className="text-sm font-mono text-on-surface">
              {calibration.sharpe.toFixed(2)}
            </span>
          </div>

          {/* Profit Factor */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-on-surface-variant">Profit Factor</span>
            <span className="text-sm font-mono text-on-surface">
              {calibration.profit_factor.toFixed(2)}x
            </span>
          </div>

          {/* Total PnL */}
          <div className="flex items-center justify-between pt-2 border-t border-ghost-border">
            <span className="text-xs text-on-surface-variant">Total PnL</span>
            <span
              className={`text-sm font-mono font-bold ${calibration.total_pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}
            >
              {calibration.total_pnl >= 0 ? "+" : ""}${calibration.total_pnl.toFixed(2)}
            </span>
          </div>
        </div>
      ) : (
        <div className="py-4 text-center">
          <p className="text-xs text-on-surface-variant">
            No resolved trades yet. Signals logged here once resolved.
          </p>
        </div>
      )}
    </GlassPanel>
  );
}

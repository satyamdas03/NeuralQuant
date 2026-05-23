"use client";

import type { CalibrationReport } from "@/lib/types";
import GlassPanel from "@/components/ui/GlassPanel";
import { History } from "lucide-react";

export default function CalibrationPanel({
  report,
  loading,
  lookbackDays,
}: {
  report: CalibrationReport | null;
  loading: boolean;
  lookbackDays: number;
}) {
  return (
    <GlassPanel>
      <h3 className="text-sm font-semibold text-on-surface flex items-center gap-2 mb-3">
        <History size={16} className="text-primary" />
        Calibration ({lookbackDays}d)
      </h3>

      {loading ? (
        <div className="space-y-2 animate-pulse">
          <div className="h-4 w-3/4 rounded bg-surface-high" />
          <div className="h-4 w-1/2 rounded bg-surface-high" />
        </div>
      ) : report && report.n_trades > 0 ? (
        <div className="space-y-2">
          {/* Hit rate bar */}
          <div className="flex items-center justify-between text-xs">
            <span className="text-on-surface-variant">Accuracy</span>
            <span className="font-mono font-semibold text-on-surface">
              {(report.hit_rate * 100).toFixed(1)}%
            </span>
          </div>
          <div className="h-1.5 rounded-full bg-surface-high overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-sky-500 to-emerald-400 transition-all"
              style={{ width: `${Math.min(report.hit_rate * 100, 100)}%` }}
            />
          </div>

          <div className="grid grid-cols-2 gap-2 mt-3">
            <div className="bg-surface-high p-2">
              <div className="text-[9px] text-on-surface-variant">Total PnL</div>
              <div className={`text-sm font-mono font-bold ${report.total_pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {report.total_pnl >= 0 ? "+" : ""}${report.total_pnl.toFixed(0)}
              </div>
            </div>
            <div className="bg-surface-high p-2">
              <div className="text-[9px] text-on-surface-variant">Profit Factor</div>
              <div className="text-sm font-mono font-bold text-on-surface">
                {report.profit_factor.toFixed(2)}x
              </div>
            </div>
            <div className="bg-surface-high p-2">
              <div className="text-[9px] text-on-surface-variant">Sharpe</div>
              <div className="text-sm font-mono font-bold text-on-surface">{report.sharpe.toFixed(2)}</div>
            </div>
            <div className="bg-surface-high p-2">
              <div className="text-[9px] text-on-surface-variant">Trades</div>
              <div className="text-sm font-mono font-bold text-on-surface">{report.n_trades}</div>
            </div>
          </div>
        </div>
      ) : (
        <p className="text-xs text-on-surface-variant py-2">
          No resolved signals yet. Run the signal_log migration and trade to build history.
        </p>
      )}
    </GlassPanel>
  );
}

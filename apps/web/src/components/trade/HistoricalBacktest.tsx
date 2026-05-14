"use client";

import type { BacktestResponse } from "@/lib/types";
import GlassPanel from "@/components/ui/GlassPanel";

function MetricCard({ label, value, suffix = "", highlight = false }: {
  label: string; value: string | number; suffix?: string; highlight?: boolean;
}) {
  return (
    <div className="rounded-lg bg-surface-high/50 border border-ghost-border px-3 py-2.5">
      <div className="text-[10px] text-on-surface-variant uppercase tracking-wide">{label}</div>
      <div className={`text-sm font-mono font-semibold mt-0.5 ${highlight ? "text-primary" : "text-on-surface"}`}>
        {value}{suffix}
      </div>
    </div>
  );
}

function EquityCurve({ data }: { data: { date: string; equity: number }[] }) {
  if (!data.length) return null;
  const W = 720;
  const H = 200;
  const pad = 28;
  const ys = data.map((d) => d.equity);
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const yRange = yMax - yMin || 1;
  const xStep = (W - 2 * pad) / Math.max(1, data.length - 1);
  const points = data
    .map((d, i) => `${pad + i * xStep},${H - pad - ((d.equity - yMin) / yRange) * (H - 2 * pad)}`)
    .join(" ");
  const up = data[data.length - 1].equity >= data[0].equity;
  const color = up ? "#4edea3" : "#ffb4ab";
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full">
      <defs>
        <linearGradient id="hbt-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.20" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline
        points={`${pad},${H - pad} ${points} ${W - pad},${H - pad}`}
        fill="url(#hbt-fill)" stroke="none"
      />
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.8" />
    </svg>
  );
}

export default function HistoricalBacktest({ data }: { data: BacktestResponse }) {
  if (data.error) {
    return (
      <GlassPanel>
        <p className="text-sm text-rose-400">{data.error}</p>
      </GlassPanel>
    );
  }

  const { metrics, equity_curve, trades } = data;
  const up = metrics.total_return_pct >= 0;

  return (
    <div className="space-y-4">
      {/* Equity curve */}
      <GlassPanel>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">
            Equity Curve ({metrics.years}yr)
          </h3>
          <span className={`text-xs font-mono ${up ? "text-tertiary" : "text-error"}`}>
            {up ? "+" : ""}{metrics.total_return_pct.toFixed(1)}%
          </span>
        </div>
        <EquityCurve data={equity_curve} />
        <p className="mt-2 text-[10px] text-on-surface-variant">
          ${metrics.initial_capital.toLocaleString()} → ${metrics.final_equity.toLocaleString()} over {metrics.n_trades} trades
        </p>
      </GlassPanel>

      {/* Metrics grid */}
      <div className="grid grid-cols-3 gap-2">
        <MetricCard label="CAGR" value={`${metrics.cagr_pct >= 0 ? "+" : ""}${metrics.cagr_pct.toFixed(1)}`} suffix="%" highlight />
        <MetricCard label="Max Drawdown" value={metrics.max_drawdown_pct.toFixed(1)} suffix="%" />
        <MetricCard label="Sharpe" value={metrics.sharpe.toFixed(2)} />
      </div>

      {/* Recent trades */}
      {trades.length > 0 && (
        <div className="max-h-48 overflow-y-auto space-y-1">
          <h4 className="text-[10px] text-on-surface-variant uppercase tracking-wide mb-1">Recent Trades</h4>
          {trades.slice(-15).reverse().map((t, i) => (
            <div key={i} className="flex items-center justify-between text-[11px] font-mono text-on-surface-variant bg-surface-high/30 rounded px-2 py-1">
              <span>{t.date}</span>
              <span className="text-primary/80">{t.ticker}</span>
              <span>{t.action}</span>
              <span>${t.price} x {t.shares}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

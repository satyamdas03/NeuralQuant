"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { authedBacktest } from "@/lib/api";
import type { BacktestResponse, Market } from "@/lib/types";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import MetricCard from "@/components/ui/MetricCard";
import GradientButton from "@/components/ui/GradientButton";
import GlassPanel from "@/components/ui/GlassPanel";
import { FlaskConical } from "lucide-react";

export const dynamic = "force-dynamic";

function BacktestForm() {
  const params = useSearchParams();
  const initialTicker = (params.get("ticker") || "AAPL").toUpperCase();
  const initialMarket = (params.get("market") || "US") as Market;

  const [ticker, setTicker] = useState(initialTicker);
  const [market, setMarket] = useState<Market>(initialMarket);
  const [fast, setFast] = useState(20);
  const [slow, setSlow] = useState(50);
  const [period, setPeriod] = useState<"1y" | "2y" | "5y" | "10y" | "max">("2y");
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setError(null);
    setLoading(true);
    setResult(null);
    try {
      const r = await authedBacktest.run({ ticker, market, fast, slow, period });
      setResult(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Backtest failed");
    } finally {
      setLoading(false);
    }
  }

  const tickerValid = /^[A-Z0-9.\-]{1,10}$/.test(ticker.trim());
  const numsValid = Number.isFinite(fast) && Number.isFinite(slow) && fast >= 2 && slow >= 5 && fast <= 200 && slow <= 400;
  const crossoverValid = fast < slow;
  const canRun = tickerValid && numsValid && crossoverValid && !loading;
  const validationMsg = !tickerValid
    ? "Ticker must be 1-10 chars (A-Z, 0-9, . or -)."
    : !numsValid
    ? "Fast SMA 2-200, Slow SMA 5-400."
    : !crossoverValid
    ? "Fast SMA must be less than Slow SMA."
    : null;

  return (
    <div className="space-y-5 p-4 lg:p-6">
      <div className="flex items-center gap-3">
        <FlaskConical size={20} className="text-secondary" />
        <div>
          <h1 className="font-headline text-xl font-bold text-on-surface">Strategy Backtest</h1>
          <p className="text-xs text-on-surface-variant">
            Vectorized SMA-crossover on daily closes. Educational only.
          </p>
        </div>
      </div>

      <GhostBorderCard>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <Input label="Ticker" value={ticker} onChange={(v) => setTicker(v.toUpperCase())} />
          <Select
            label="Market"
            value={market}
            onChange={(v) => setMarket(v as Market)}
            options={[{ value: "US", label: "US" }, { value: "IN", label: "India" }]}
          />
          <NumberInput label="Fast SMA" value={fast} onChange={setFast} min={2} max={200} />
          <NumberInput label="Slow SMA" value={slow} onChange={setSlow} min={5} max={400} />
          <Select
            label="Period"
            value={period}
            onChange={(v) => setPeriod(v as typeof period)}
            options={[
              { value: "1y", label: "1 year" },
              { value: "2y", label: "2 years" },
              { value: "5y", label: "5 years" },
              { value: "10y", label: "10 years" },
              { value: "max", label: "Max" },
            ]}
          />
        </div>
        <div className="mt-4 flex items-center gap-4">
          <GradientButton onClick={run} disabled={!canRun} size="md">
            {loading ? "Running…" : "Run backtest"}
          </GradientButton>
          {validationMsg && <p className="text-xs text-primary">{validationMsg}</p>}
          {error && <p className="text-sm text-error">{error}</p>}
        </div>
      </GhostBorderCard>

      {result && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <MetricCard
              label="Strategy Return"
              value={`${result.total_return_pct >= 0 ? "+" : ""}${result.total_return_pct.toFixed(2)}%`}
              accent={result.total_return_pct >= 0 ? "tertiary" : "error"}
            />
            <MetricCard
              label="Buy & Hold"
              value={`${result.buy_hold_return_pct >= 0 ? "+" : ""}${result.buy_hold_return_pct.toFixed(2)}%`}
              accent={result.buy_hold_return_pct >= 0 ? "tertiary" : "error"}
            />
            <MetricCard label="Sharpe" value={result.sharpe.toFixed(2)} accent="secondary" />
            <MetricCard
              label="Max Drawdown"
              value={`${result.max_drawdown_pct.toFixed(2)}%`}
              accent="error"
            />
          </div>

          <GlassPanel>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-headline text-sm font-semibold text-on-surface uppercase tracking-wide">
                Equity curve · {result.ticker}
              </h2>
              <span className="text-xs text-on-surface-variant">
                {result.n_trades} trades · {result.n_days} days
              </span>
            </div>
            <EquityChart data={result.equity_curve} />
            <p className="mt-3 text-xs text-on-surface-variant">
              {result.total_return_pct > result.buy_hold_return_pct
                ? "Strategy beat buy-and-hold."
                : "Buy-and-hold outperformed the strategy."}{" "}
              Final equity: ${result.final_equity.toLocaleString()}.
            </p>
          </GlassPanel>
        </div>
      )}
    </div>
  );
}

function Input({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-on-surface-variant">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg bg-surface-high px-3 py-2 text-sm text-on-surface outline-none focus:ring-1 focus:ring-primary"
      />
    </label>
  );
}

function NumberInput({ label, value, onChange, min, max }: {
  label: string; value: number; onChange: (v: number) => void; min: number; max: number;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-on-surface-variant">{label}</span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        onChange={(e) => {
          const n = Number(e.target.value);
          onChange(Number.isFinite(n) ? n : 0);
        }}
        className="w-full rounded-lg bg-surface-high px-3 py-2 text-sm text-on-surface outline-none focus:ring-1 focus:ring-primary tabular-nums"
      />
    </label>
  );
}

function Select({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[];
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-on-surface-variant">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg bg-surface-high px-3 py-2 text-sm text-on-surface outline-none focus:ring-1 focus:ring-primary"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}

function EquityChart({ data }: { data: { date: string; equity: number }[] }) {
  if (!data.length) return null;
  const W = 720;
  const H = 220;
  const pad = 28;
  const ys = data.map((d) => d.equity);
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const yRange = yMax - yMin || 1;
  const xStep = (W - 2 * pad) / Math.max(1, data.length - 1);
  const points = data
    .map((d, i) => `${pad + i * xStep},${H - pad - ((d.equity - yMin) / yRange) * (H - 2 * pad)}`)
    .join(" ");
  const last = data[data.length - 1];
  const first = data[0];
  const up = last.equity >= first.equity;
  const lineColor = up ? "#4edea3" : "#ffb4ab";
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full">
      <defs>
        <linearGradient id="eq-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={lineColor} stopOpacity="0.25" />
          <stop offset="100%" stopColor={lineColor} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline
        points={`${pad},${H - pad} ${points} ${W - pad},${H - pad}`}
        fill="url(#eq-fill)"
        stroke="none"
      />
      <polyline points={points} fill="none" stroke={lineColor} strokeWidth="1.8" />
      <text x={pad} y={H - 8} className="fill-on-surface-variant" fontSize="10">{first.date}</text>
      <text x={W - pad} y={H - 8} textAnchor="end" className="fill-on-surface-variant" fontSize="10">{last.date}</text>
    </svg>
  );
}

export default function BacktestPage() {
  return (
    <Suspense fallback={null}>
      <BacktestForm />
    </Suspense>
  );
}
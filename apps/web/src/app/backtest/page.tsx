"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { authedBacktest } from "@/lib/api";
import type { BacktestResponse, Market } from "@/lib/types";

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

  const beatBH = result && result.total_return_pct > result.buy_hold_return_pct;

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
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Strategy Backtest</h1>
        <p className="text-sm text-gray-400 mt-1">
          Vectorized SMA-crossover on daily closes. Fast MA &gt; Slow MA ⇒ long, else flat.
          No slippage/commission modeled. Educational only.
        </p>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Input label="Ticker" value={ticker} onChange={(v) => setTicker(v.toUpperCase())} />
          <Select
            label="Market"
            value={market}
            onChange={(v) => setMarket(v as Market)}
            options={[
              { value: "US", label: "US" },
              { value: "IN", label: "India" },
            ]}
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
        <button
          onClick={run}
          disabled={!canRun}
          className="px-6 py-2.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 rounded-lg text-sm font-medium transition-colors"
        >
          {loading ? "Running…" : "Run backtest"}
        </button>
        {validationMsg && <p className="text-xs text-amber-400">{validationMsg}</p>}
        {error && <p className="text-sm text-red-400">{error}</p>}
      </div>

      {result && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Metric
              label="Strategy Return"
              value={`${result.total_return_pct >= 0 ? "+" : ""}${result.total_return_pct.toFixed(2)}%`}
              accent={result.total_return_pct >= 0 ? "emerald" : "red"}
            />
            <Metric
              label="Buy & Hold"
              value={`${result.buy_hold_return_pct >= 0 ? "+" : ""}${result.buy_hold_return_pct.toFixed(2)}%`}
              accent={result.buy_hold_return_pct >= 0 ? "emerald" : "red"}
            />
            <Metric label="Sharpe" value={result.sharpe.toFixed(2)} />
            <Metric
              label="Max Drawdown"
              value={`${result.max_drawdown_pct.toFixed(2)}%`}
              accent="red"
            />
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-sm text-gray-300 uppercase tracking-wide">
                Equity curve · {result.ticker}
              </h2>
              <span className="text-xs text-gray-500">
                {result.n_trades} trades · {result.n_days} trading days
              </span>
            </div>
            <EquityChart data={result.equity_curve} />
            <p className="text-xs text-gray-500 mt-3">
              {beatBH ? "Strategy beat buy-and-hold." : "Buy-and-hold outperformed the strategy."} Final equity: ${result.final_equity.toLocaleString()}.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function Input({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="block">
      <span className="block text-xs text-gray-500 mb-1">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-violet-500"
      />
    </label>
  );
}

function NumberInput({ label, value, onChange, min, max }: {
  label: string; value: number; onChange: (v: number) => void; min: number; max: number;
}) {
  return (
    <label className="block">
      <span className="block text-xs text-gray-500 mb-1">{label}</span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        onChange={(e) => {
          const n = Number(e.target.value);
          onChange(Number.isFinite(n) ? n : 0);
        }}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-violet-500 tabular-nums"
      />
    </label>
  );
}

function Select({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[];
}) {
  return (
    <label className="block">
      <span className="block text-xs text-gray-500 mb-1">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-violet-500"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}

function Metric({ label, value, accent }: { label: string; value: string; accent?: "emerald" | "red" }) {
  const color = accent === "emerald" ? "text-emerald-400" : accent === "red" ? "text-red-400" : "text-gray-100";
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="text-xs text-gray-500 uppercase tracking-wide">{label}</div>
      <div className={`text-2xl font-bold mt-1 tabular-nums ${color}`}>{value}</div>
    </div>
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
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto">
      <defs>
        <linearGradient id="eq-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={up ? "#10b981" : "#ef4444"} stopOpacity="0.25" />
          <stop offset="100%" stopColor={up ? "#10b981" : "#ef4444"} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline
        points={`${pad},${H - pad} ${points} ${W - pad},${H - pad}`}
        fill="url(#eq-fill)"
        stroke="none"
      />
      <polyline points={points} fill="none" stroke={up ? "#10b981" : "#ef4444"} strokeWidth="1.8" />
      <text x={pad} y={H - 8} className="fill-gray-500" fontSize="10">{first.date}</text>
      <text x={W - pad} y={H - 8} textAnchor="end" className="fill-gray-500" fontSize="10">{last.date}</text>
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

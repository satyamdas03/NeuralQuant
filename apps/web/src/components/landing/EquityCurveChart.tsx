"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

const DATA = [
  { date: "Apr 1", strategy: 0, benchmark: 0 },
  { date: "Apr 7", strategy: 2.1, benchmark: 1.2 },
  { date: "Apr 14", strategy: 4.8, benchmark: 2.3 },
  { date: "Apr 21", strategy: 3.9, benchmark: 1.8 },
  { date: "Apr 28", strategy: 6.7, benchmark: 3.1 },
  { date: "May 5", strategy: 9.2, benchmark: 4.4 },
  { date: "May 12", strategy: 11.4, benchmark: 5.6 },
  { date: "May 19", strategy: 13.1, benchmark: 6.2 },
  { date: "May 26", strategy: 16.8, benchmark: 7.8 },
  { date: "Jun 2", strategy: 18.9, benchmark: 8.5 },
  { date: "Jun 9", strategy: 20.4, benchmark: 9.1 },
  { date: "Jun 16", strategy: 22.1, benchmark: 9.8 },
  { date: "Jun 23", strategy: 23.6, benchmark: 10.4 },
  { date: "Jun 30", strategy: 24.8, benchmark: 11.3 },
];

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;

  const strategy = payload.find((p: { dataKey: string }) => p.dataKey === "strategy")?.value ?? 0;
  const benchmark = payload.find((p: { dataKey: string }) => p.dataKey === "benchmark")?.value ?? 0;
  const alpha = (strategy - benchmark).toFixed(2);

  return (
    <div
      className="px-4 py-3 text-xs border"
      style={{
        background: "var(--color-surface-container)",
        borderColor: "var(--color-border-glow)",
        boxShadow: "0 4px 24px rgba(0,0,0,0.4)",
      }}
    >
      <p className="font-mono text-[10px] font-bold tracking-[0.15em] uppercase text-text-muted mb-2">
        {label}
      </p>
      <div className="space-y-1">
        <div className="flex items-center justify-between gap-6">
          <span className="flex items-center gap-2 text-text-primary">
            <span className="w-2 h-[2px] bg-primary" />
            Strategy
          </span>
          <span className="font-mono font-bold text-primary tabular-nums">
            +{strategy.toFixed(1)}%
          </span>
        </div>
        <div className="flex items-center justify-between gap-6">
          <span className="flex items-center gap-2 text-text-primary">
            <span className="w-2 h-[2px] bg-text-muted" />
            Benchmark
          </span>
          <span className="font-mono font-bold text-text-muted tabular-nums">
            +{benchmark.toFixed(1)}%
          </span>
        </div>
        <div className="flex items-center justify-between gap-6 pt-1 mt-1"
          style={{ borderTop: "1px solid rgba(0, 255, 178, 0.15)" }}
        >
          <span className="text-text-muted">Alpha</span>
          <span className="font-mono font-bold text-tertiary-fixed-dim tabular-nums">
            +{alpha}%
          </span>
        </div>
      </div>
    </div>
  );
}

export default function EquityCurveChart() {
  return (
    <div
      className="w-full p-6 md:p-8 border"
      style={{
        background: "var(--color-surface)",
        borderColor: "var(--color-ghost-border)",
      }}
    >
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h3 className="font-headline text-xl md:text-2xl font-bold text-text-primary">
            Equity Curve
          </h3>
          <p className="mt-1 font-mono text-[11px] text-text-muted">
            Cumulative returns — Strategy vs NIFTY50 Benchmark
          </p>
        </div>
        <div className="flex items-center gap-4 font-mono text-[11px]">
          <span className="flex items-center gap-2 text-text-muted">
            <span className="w-4 h-[2px] bg-primary" />
            Strategy
          </span>
          <span className="flex items-center gap-2 text-text-muted">
            <span className="w-4 h-[2px] bg-text-muted border-dashed" style={{ borderTop: "2px dashed var(--color-text-muted)" }} />
            Benchmark
          </span>
        </div>
      </div>

      <div className="w-full" style={{ height: 360 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={DATA} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--color-surface-high)"
              vertical={false}
            />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}
              axisLine={{ stroke: "var(--color-surface-high)" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) => `${v}%`}
              width={48}
            />
            <Tooltip content={<CustomTooltip />} />
            <Line
              type="monotone"
              dataKey="strategy"
              stroke="var(--color-primary)"
              strokeWidth={2.5}
              dot={false}
              activeDot={{ r: 5, fill: "var(--color-primary)", strokeWidth: 0 }}
            />
            <Line
              type="monotone"
              dataKey="benchmark"
              stroke="var(--color-text-muted)"
              strokeWidth={2}
              strokeDasharray="6 4"
              dot={false}
              activeDot={{ r: 4, fill: "var(--color-text-muted)", strokeWidth: 0 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

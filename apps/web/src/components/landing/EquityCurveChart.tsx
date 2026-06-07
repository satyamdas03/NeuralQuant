"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

interface DataPoint {
  pct: number;
  return: number;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;

  const point = payload.find((p: { dataKey: string }) => p.dataKey === "return")?.value ?? 0;

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
            Return
          </span>
          <span className="font-mono font-bold text-primary tabular-nums">
            {point >= 0 ? "+" : ""}{point.toFixed(1)}%
          </span>
        </div>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="w-full p-6 md:p-8 border flex flex-col items-center justify-center gap-3" style={{ background: "var(--color-surface)", borderColor: "var(--color-ghost-border)" }}>
      <div className="h-2 w-24 bg-surface-high rounded animate-pulse" />
      <p className="font-mono text-[11px] text-text-muted">Backtest results loading…</p>
    </div>
  );
}

export default function EquityCurveChart({
  data,
  benchmark,
}: {
  data?: Array<DataPoint> | null;
  benchmark?: number | null;
}) {
  if (!data || data.length === 0) {
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
              Return Distribution
            </h3>
            <p className="mt-1 font-mono text-[11px] text-text-muted">
              Individual selection returns — Q1 FY2027
            </p>
          </div>
        </div>
        <EmptyState />
      </div>
    );
  }

  // Transform percentile distribution data for the chart
  const chartData = data.map((d) => ({
    label: `${d.pct.toFixed(0)}%`,
    return: d.return,
  }));

  const benchmarkValue = benchmark ?? 0;

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
            Return Distribution
          </h3>
          <p className="mt-1 font-mono text-[11px] text-text-muted">
            Individual selection returns vs NIFTY50 Benchmark
          </p>
        </div>
        <div className="flex items-center gap-4 font-mono text-[11px]">
          <span className="flex items-center gap-2 text-text-muted">
            <span className="w-4 h-[2px] bg-primary" />
            Selections
          </span>
          {benchmark !== null && benchmark !== undefined && (
            <span className="flex items-center gap-2 text-text-muted">
              <span className="w-4 h-[2px] bg-text-muted border-dashed" style={{ borderTop: "2px dashed var(--color-text-muted)" }} />
              Benchmark
            </span>
          )}
        </div>
      </div>

      <div className="w-full" style={{ height: 360 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--color-surface-high)"
              vertical={false}
            />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 11, fill: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}
              axisLine={{ stroke: "var(--color-surface-high)" }}
              tickLine={false}
              label={{ value: "Percentile", position: "insideBottom", offset: -2, fontSize: 10, fill: "var(--color-text-muted)" }}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) => `${v}%`}
              width={48}
            />
            <Tooltip content={<CustomTooltip />} />
            {benchmark !== null && benchmark !== undefined && (
              <ReferenceLine
                y={benchmarkValue}
                stroke="var(--color-text-muted)"
                strokeDasharray="6 4"
                strokeWidth={2}
              />
            )}
            <Line
              type="monotone"
              dataKey="return"
              stroke="var(--color-primary)"
              strokeWidth={2.5}
              dot={{ r: 3, fill: "var(--color-primary)", strokeWidth: 0 }}
              activeDot={{ r: 5, fill: "var(--color-primary)", strokeWidth: 0 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

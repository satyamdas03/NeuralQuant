"use client";
import { useEffect, useState } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from "recharts";
import { api } from "@/lib/api";
import type { ChartBar, Market } from "@/lib/types";
import GhostBorderCard from "@/components/ui/GhostBorderCard";

const PERIODS = ["1d", "5d", "1mo", "3mo", "1y", "5y"] as const;
type Period = typeof PERIODS[number];

function CustomTooltip({ active, payload, label, symbol }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-surface-container ghost-border rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-on-surface-variant mb-1">{label}</p>
      <p className="font-semibold text-on-surface">{symbol}{payload[0].value.toFixed(2)}</p>
    </div>
  );
}

export function PriceChart({ ticker, market = "US" }: { ticker: string; market?: Market }) {
  const symbol = market === "IN" ? "₹" : "$";
  const [period, setPeriod] = useState<Period>("1mo");
  const [data, setData] = useState<ChartBar[]>([]);
  const [pctChange, setPctChange] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.getStockChart(ticker, period, market)
      .then(d => { setData(d.data); setPctChange(d.period_change_pct); })
      .catch(() => { setData([]); })
      .finally(() => setLoading(false));
  }, [ticker, period, market]);

  const positive = pctChange >= 0;
  const color = positive ? "#4edea3" : "#ffb4ab";

  const tickCount = Math.min(data.length, period === "1d" ? 8 : period === "5d" ? 8 : 6);
  const tickStep = Math.ceil(data.length / tickCount);
  const ticks = data.filter((_, i) => i % tickStep === 0).map(d => d.date);

  return (
    <GhostBorderCard>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="font-semibold text-on-surface text-sm">Price</span>
          {!loading && data.length > 0 && (
            <>
              <span className={`text-sm font-bold tabular-nums ${positive ? "text-tertiary" : "text-error"}`}>
                {symbol}{data[data.length - 1]?.close.toFixed(2)}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded-full ${positive ? "bg-tertiary/10 text-tertiary" : "bg-error/10 text-error"}`}>
                {positive ? "+" : ""}{pctChange.toFixed(2)}%
              </span>
            </>
          )}
        </div>
        <div className="flex gap-0.5">
          {PERIODS.map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-2.5 py-1 text-xs rounded-md font-medium transition-colors ${
                period === p
                  ? "bg-primary text-on-surface"
                  : "text-on-surface-variant hover:text-on-surface hover:bg-surface-high"
              }`}
            >
              {p.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="h-48 bg-surface-container rounded-lg animate-pulse" />
      ) : data.length === 0 ? (
        <div className="h-48 flex items-center justify-center text-on-surface-variant text-sm">
          No chart data available
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id={`grad-${ticker}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor={color} stopOpacity={0.25} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-high)" vertical={false} />
            <XAxis
              dataKey="date"
              ticks={ticks}
              tick={{ fontSize: 10, fill: "var(--on-surface-variant)" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fontSize: 10, fill: "var(--on-surface-variant)" }}
              axisLine={false}
              tickLine={false}
              tickFormatter={v => `${symbol}${v}`}
              width={50}
            />
            <Tooltip content={<CustomTooltip symbol={symbol} />} />
            <Area
              type="monotone"
              dataKey="close"
              stroke={color}
              strokeWidth={2}
              fill={`url(#grad-${ticker})`}
              dot={false}
              activeDot={{ r: 4, fill: color, strokeWidth: 0 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </GhostBorderCard>
  );
}
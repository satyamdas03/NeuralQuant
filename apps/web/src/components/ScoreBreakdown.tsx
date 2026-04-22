"use client";
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer } from "recharts";
import type { SubScores } from "@/lib/types";

export function ScoreBreakdown({ scores }: { scores: SubScores }) {
  const data = [
    { factor: "Quality",  value: Math.round(scores.quality * 100) },
    { factor: "Momentum", value: Math.round(scores.momentum * 100) },
    { factor: "Value",    value: Math.round(scores.value * 100) },
    { factor: "Low Vol",  value: Math.round(scores.low_vol * 100) },
    { factor: "SI",       value: Math.round(scores.short_interest * 100) },
  ];

  return (
    <div className="p-5 rounded-2xl ghost-border bg-surface-low/60">
      <h3 className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-2">
        Factor Breakdown
      </h3>
      <ResponsiveContainer width="100%" height={220}>
        <RadarChart data={data}>
          <PolarGrid stroke="var(--surface-high)" />
          <PolarAngleAxis dataKey="factor" tick={{ fill: "var(--on-surface-variant)", fontSize: 12 }} />
          <Radar
            dataKey="value" fill="#c1c1ff" fillOpacity={0.2}
            stroke="#c1c1ff" strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
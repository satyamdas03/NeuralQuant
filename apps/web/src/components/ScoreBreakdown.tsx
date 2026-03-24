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
    <div className="p-5 rounded-2xl border border-gray-800 bg-gray-900/60">
      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-2">
        Factor Breakdown
      </h3>
      <ResponsiveContainer width="100%" height={220}>
        <RadarChart data={data}>
          <PolarGrid stroke="#1f2937" />
          <PolarAngleAxis dataKey="factor" tick={{ fill: "#9ca3af", fontSize: 12 }} />
          <Radar
            dataKey="value" fill="#7c3aed" fillOpacity={0.25}
            stroke="#7c3aed" strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

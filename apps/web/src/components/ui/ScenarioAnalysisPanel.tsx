"use client";

import type { ScenarioCard } from "@/lib/types";

const SCENARIO_COLORS: Record<string, string> = {
  Bull: "#22c55e",
  Base: "#6366f1",
  Bear: "#ef4444",
};

export default function ScenarioAnalysisPanel({
  scenarios,
}: {
  scenarios: ScenarioCard[];
}) {
  if (!scenarios || scenarios.length === 0) return null;

  return (
    <div className="space-y-3">
      <div className="text-xs font-medium text-on-surface-variant uppercase tracking-wide">
        Scenario Analysis
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {scenarios.map((s, i) => {
          const color = s.color || SCENARIO_COLORS[s.label] || "#6366f1";
          const prob = s.probability_pct ?? 0;
          return (
            <div
              key={i}
              className="rounded-xl bg-surface-high border border-outline/30 p-3 space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold" style={{ color }}>
                  {s.label}
                </span>
                <span className="text-xs text-on-surface-variant">{prob}%</span>
              </div>
              <div className="h-2 w-full rounded-full bg-surface-container overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${Math.min(100, prob)}%`, backgroundColor: color }}
                />
              </div>
              {s.outcome && (
                <div className="text-sm font-medium text-on-surface">{s.outcome}</div>
              )}
              {s.description && (
                <p className="text-xs text-on-surface-variant leading-snug">{s.description}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

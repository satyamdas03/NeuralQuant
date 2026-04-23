"use client";

import type { RegimeLabel } from "@/lib/types";
import RegimeBadge from "@/components/ui/RegimeBadge";
import GlassPanel from "@/components/ui/GlassPanel";

const REGIME_DESCRIPTIONS: Record<RegimeLabel, string> = {
  "Risk-On":
    "Broad-based rally environment. Growth and momentum factors typically outperform. Risk assets are favoured.",
  "Late-Cycle":
    "Expansion maturing, volatility rising. Value and quality become more defensive. Momentum fades.",
  Bear: "Risk-off environment. Quality and low-volatility are up-weighted for capital preservation. Momentum is penalised.",
  Recovery:
    "Early expansion post-downturn. Value and momentum rebound. Low-volatility exposure is reduced.",
};

const REGIME_ADJUSTMENTS: Record<RegimeLabel, string> = {
  "Risk-On":
    "Momentum up-weighted, Low Vol down-weighted. Short interest & insider signals unchanged.",
  "Late-Cycle":
    "Value up-weighted, Momentum down-weighted. Quality slightly reduced.",
  Bear: "Quality up-weighted, Low Vol up-weighted, Momentum down-weighted. Defensive tilt.",
  Recovery:
    "Value up-weighted, Momentum neutral, Low Vol down-weighted. Cyclical tilt.",
};

const REGIME_CYCLE: RegimeLabel[] = ["Risk-On", "Late-Cycle", "Bear", "Recovery"];

export function RegimeContextPanel({ regime }: { regime: RegimeLabel }) {
  return (
    <GlassPanel className="flex flex-col md:flex-row md:items-center gap-4 md:gap-6">
      {/* Left: badge + description */}
      <div className="flex-1 space-y-2">
        <div className="flex items-center gap-3">
          <RegimeBadge regime={regime} />
          <span className="text-xs text-on-surface-variant">Current Market Regime</span>
        </div>
        <p className="text-sm text-on-surface leading-relaxed">
          {REGIME_DESCRIPTIONS[regime]}
        </p>
        <p className="text-xs text-on-surface-variant">
          <span className="text-primary font-medium">Regime adjustment:</span>{" "}
          {REGIME_ADJUSTMENTS[regime]}
        </p>
      </div>

      {/* Right: cycle timeline */}
      <div className="md:w-64 shrink-0">
        <div className="flex items-center justify-between text-[10px] text-on-surface-variant mb-1.5 uppercase tracking-wider">
          <span>Regime Cycle</span>
        </div>
        <div className="relative flex items-center">
          {/* Connecting line */}
          <div className="absolute left-0 right-0 top-1/2 -translate-y-1/2 h-0.5 bg-surface-high" />
          {REGIME_CYCLE.map((r) => {
            const active = r === regime;
            return (
              <div key={r} className="relative flex-1 flex flex-col items-center">
                <div
                  className={`z-10 h-3 w-3 rounded-full border-2 transition-all ${
                    active
                      ? "border-primary bg-primary scale-125"
                      : "border-surface-high bg-surface-container"
                  }`}
                />
                <span
                  className={`mt-1.5 text-[10px] font-medium ${
                    active ? "text-primary" : "text-on-surface-variant"
                  }`}
                >
                  {r}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </GlassPanel>
  );
}

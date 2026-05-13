"use client";

import type { TradeStrategy } from "@/lib/types";
import GlassPanel from "@/components/ui/GlassPanel";
import {
  TrendingUp,
  DollarSign,
  Banknote,
  Gem,
  RotateCcw,
  Globe,
  Check,
} from "lucide-react";

const ICON_MAP: Record<string, React.ElementType> = {
  TrendingUp,
  DollarSign,
  Banknote,
  Gem,
  RotateCcw,
  Globe,
};

const RISK_COLORS: Record<string, string> = {
  conservative: "bg-sky-500/10 text-sky-400 border-sky-500/25",
  balanced: "bg-amber-500/10 text-amber-400 border-amber-500/25",
  aggressive: "bg-rose-500/10 text-rose-400 border-rose-500/25",
};

export default function StrategyCard({
  strategies,
  selectedId,
  onSelect,
  loading,
}: {
  strategies: TradeStrategy[];
  selectedId: string;
  onSelect: (id: string) => void;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 animate-pulse">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-24 rounded-xl bg-surface-high" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
      {strategies.map((s) => {
        const Icon = ICON_MAP[s.icon] || TrendingUp;
        const selected = s.id === selectedId;

        return (
          <button
            key={s.id}
            onClick={() => onSelect(s.id)}
            className={`text-left transition-all duration-200 rounded-xl border p-3 ${
              selected
                ? "border-primary/40 bg-primary/5 shadow-[0_0_12px_rgba(193,193,255,0.08)]"
                : "border-ghost-border glass hover:border-primary/20 hover:bg-surface-high"
            }`}
          >
            <div className="flex items-center justify-between mb-1">
              <Icon
                size={18}
                className={selected ? "text-primary" : "text-on-surface-variant"}
              />
              {selected && <Check size={14} className="text-primary" />}
            </div>
            <div className="text-[13px] font-semibold text-on-surface">{s.name}</div>
            <div className="text-[10px] text-on-surface-variant mt-0.5 line-clamp-2">
              {s.description}
            </div>
            <div className="mt-2 flex items-center gap-2">
              <span
                className={`text-[9px] px-1.5 py-0.5 rounded-full border font-medium ${RISK_COLORS[s.risk_profile] || RISK_COLORS.balanced}`}
              >
                {s.risk_profile}
              </span>
              <span className="text-[9px] text-on-surface-variant">
                {s.max_positions} pos &middot; ${s.max_bet} max
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

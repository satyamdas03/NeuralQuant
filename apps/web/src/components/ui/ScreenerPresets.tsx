"use client";

import { PRESETS, type ScreenerPreset } from "@/data/screener-presets";
import { TrendingUp, DollarSign, Banknote, Gem, RotateCcw, LayoutGrid } from "lucide-react";

const ICON_MAP: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  TrendingUp, DollarSign, Banknote, Gem, RotateCcw,
};

type Props = {
  active: string | null;
  onSelect: (preset: ScreenerPreset | null) => void;
};

export default function ScreenerPresets({ active, onSelect }: Props) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
      <button
        onClick={() => onSelect(null)}
        className={`shrink-0 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
          active === null
            ? "bg-primary/20 text-primary ghost-border"
            : "text-on-surface-variant hover:bg-surface-high"
        }`}
      >
        <LayoutGrid size={14} className="inline mr-1" />
        All Stocks
      </button>
      {PRESETS.map((p) => {
        const Icon = ICON_MAP[p.icon] ?? TrendingUp;
        return (
          <button
            key={p.id}
            onClick={() => onSelect(p)}
            className={`shrink-0 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
              active === p.id
                ? "bg-primary/20 text-primary ghost-border"
                : "text-on-surface-variant hover:bg-surface-high"
            }`}
            title={p.description}
          >
            <Icon size={14} className="inline mr-1" />
            {p.name}
          </button>
        );
      })}
    </div>
  );
}
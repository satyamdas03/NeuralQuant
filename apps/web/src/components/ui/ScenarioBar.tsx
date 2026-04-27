import type { ScenarioItem } from "@/lib/types";

const LABEL_COLORS: Record<string, string> = {
  Bear: "text-red-400 bg-red-500/10",
  Base: "text-amber-400 bg-amber-500/10",
  Bull: "text-emerald-400 bg-emerald-500/10",
};

type Props = { scenarios: ScenarioItem[] };

export default function ScenarioBar({ scenarios }: Props) {
  if (!scenarios.length) return null;
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">Scenarios</p>
      {scenarios.map((s, i) => {
        const colors = LABEL_COLORS[s.label] ?? LABEL_COLORS.Base;
        return (
          <div key={i} className={`rounded-lg ${colors} ghost-border px-3 py-2`}>
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium">{s.label}</span>
              <span className="text-xs font-semibold">{s.target}</span>
            </div>
            <div className="mt-1 flex items-center gap-2">
              <div className="flex-1 h-1 rounded-full bg-surface-container overflow-hidden">
                <div className="h-full rounded-full bg-current opacity-40" style={{ width: `${s.probability * 100}%` }} />
              </div>
              <span className="text-[10px] opacity-70">{(s.probability * 100).toFixed(0)}%</span>
            </div>
            <p className="text-[10px] opacity-60 mt-1">{s.thesis}</p>
          </div>
        );
      })}
    </div>
  );
}
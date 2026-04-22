import type { FeatureDriver } from "@/lib/types";

export function FeatureAttribution({ drivers }: { drivers: FeatureDriver[] }) {
  return (
    <div className="p-5 rounded-2xl ghost-border bg-surface-low/60">
      <h3 className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-4">
        Score Drivers
      </h3>
      <div className="space-y-3">
        {drivers.map((d) => (
          <div key={d.name} className="flex items-center gap-3">
            <span className="text-sm text-on-surface w-40 flex-shrink-0">{d.name}</span>
            <div className="flex-1 h-2 bg-surface-high rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  d.direction === "positive" ? "bg-tertiary" :
                  d.direction === "negative" ? "bg-error" : "bg-on-surface-variant"
                }`}
                style={{ width: `${Math.abs(d.contribution) * 100}%` }}
              />
            </div>
            <span className={`text-xs w-16 text-right font-mono ${
              d.direction === "positive" ? "text-tertiary" :
              d.direction === "negative" ? "text-error" : "text-on-surface-variant"
            }`}>
              {d.contribution > 0 ? "+" : ""}{(d.contribution * 100).toFixed(0)}
            </span>
            <span className="text-xs text-on-surface-variant w-16 text-right">{d.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
import type { FeatureDriver } from "@/lib/types";

export function FeatureAttribution({ drivers }: { drivers: FeatureDriver[] }) {
  return (
    <div className="p-5 rounded-2xl border border-gray-800 bg-gray-900/60">
      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
        Score Drivers
      </h3>
      <div className="space-y-3">
        {drivers.map((d) => (
          <div key={d.name} className="flex items-center gap-3">
            <span className="text-sm text-gray-300 w-40 flex-shrink-0">{d.name}</span>
            <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  d.direction === "positive" ? "bg-green-500" :
                  d.direction === "negative" ? "bg-red-500" : "bg-gray-500"
                }`}
                style={{ width: `${Math.abs(d.contribution) * 100}%` }}
              />
            </div>
            <span className={`text-xs w-16 text-right font-mono ${
              d.direction === "positive" ? "text-green-400" :
              d.direction === "negative" ? "text-red-400" : "text-gray-500"
            }`}>
              {d.contribution > 0 ? "+" : ""}{(d.contribution * 100).toFixed(0)}
            </span>
            <span className="text-xs text-gray-500 w-16 text-right">{d.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

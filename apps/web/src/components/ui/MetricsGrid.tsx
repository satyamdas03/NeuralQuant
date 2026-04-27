import type { MetricItem } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  positive: "text-emerald-400",
  negative: "text-red-400",
  neutral: "text-on-surface-variant",
};

type Props = { metrics: MetricItem[] };

export default function MetricsGrid({ metrics }: Props) {
  if (!metrics.length) return null;
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
      {metrics.map((m, i) => (
        <div key={i} className="rounded-lg bg-surface-low/40 ghost-border px-3 py-2">
          <p className="text-[10px] text-on-surface-variant uppercase tracking-wide">{m.name}</p>
          <p className={`text-sm font-semibold ${STATUS_COLORS[m.status]}`}>{m.value}</p>
          {m.benchmark && (
            <p className="text-[10px] text-on-surface-variant mt-0.5">vs {m.benchmark}</p>
          )}
        </div>
      ))}
    </div>
  );
}
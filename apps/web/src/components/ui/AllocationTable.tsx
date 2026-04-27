import type { AllocationItem } from "@/lib/types";

type Props = { allocations: AllocationItem[] };

export default function AllocationTable({ allocations }: Props) {
  if (!allocations.length) return null;
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">Portfolio Allocation</p>
      <div className="space-y-1.5">
        {allocations.map((a, i) => (
          <div key={i} className="rounded-lg bg-surface-low/40 ghost-border px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-on-surface">{a.ticker}</span>
              <span className="text-sm tabular-nums font-medium text-primary">{a.weight}%</span>
            </div>
            <p className="text-[10px] text-on-surface-variant mt-1">{a.rationale}</p>
            <p className="text-[10px] text-red-400/80 mt-0.5">Alt: {a.why_not_alt}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
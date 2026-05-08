"use client";

import type { AllocationSegment } from "@/lib/types";

export default function AllocationBar({
  segments,
}: {
  segments: AllocationSegment[];
}) {
  if (!segments || segments.length === 0) return null;

  const total = segments.reduce((s, x) => s + (x.percentage || 0), 0);
  const warn = Math.abs(total - 100) > 1;

  return (
    <div className="space-y-2">
      <div className="flex h-4 w-full overflow-hidden rounded-full">
        {segments.map((seg, i) => (
          <div
            key={i}
            style={{
              width: `${Math.max(0, Math.min(100, seg.percentage))}%`,
              backgroundColor: seg.color || "#6366f1",
            }}
            className="first:rounded-l-full last:rounded-r-full"
            title={`${seg.label}: ${seg.percentage}%${seg.rationale ? " — " + seg.rationale : ""}`}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        {segments.map((seg, i) => (
          <div key={i} className="flex items-center gap-1.5 text-xs">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ backgroundColor: seg.color || "#6366f1" }}
            />
            <span className="text-on-surface font-medium">{seg.label}</span>
            <span className="text-on-surface-variant">{seg.percentage}%</span>
          </div>
        ))}
      </div>
      {warn && (
        <div className="rounded bg-amber-500/10 px-2 py-1 text-[10px] text-amber-400 border border-amber-500/20">
          Allocation sums to {total.toFixed(1)}% (expected 100%)
        </div>
      )}
    </div>
  );
}

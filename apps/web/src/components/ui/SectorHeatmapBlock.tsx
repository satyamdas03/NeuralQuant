import type { SectorData } from "@/lib/types";

type Props = {
  sectors: SectorData[];
};

export default function SectorHeatmapBlock({ sectors }: Props) {
  const maxAbs = Math.max(...sectors.map((s) => Math.abs(s.change_pct)), 1);

  return (
    <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3 lg:grid-cols-4">
      {sectors.map((s) => {
        const intensity = Math.abs(s.change_pct) / maxAbs;
        const bg =
          s.change_pct >= 0
            ? `rgba(78, 222, 163, ${0.15 + intensity * 0.35})`
            : `rgba(255, 180, 171, ${0.15 + intensity * 0.35})`;
        const text =
          s.change_pct >= 0 ? "text-tertiary" : "text-error";

        return (
          <div
            key={s.symbol}
            className="rounded-lg p-2 text-center"
            style={{ background: bg }}
          >
            <p className="text-xs text-on-surface-variant truncate">
              {s.name}
            </p>
            <p className={`tabular-nums text-sm font-semibold ${text}`}>
              {s.change_pct >= 0 ? "+" : ""}
              {s.change_pct.toFixed(2)}%
            </p>
          </div>
        );
      })}
    </div>
  );
}
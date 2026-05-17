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
            ? `rgba(0, 255, 178, ${0.15 + intensity * 0.35})`
            : `rgba(255, 65, 88, ${0.15 + intensity * 0.35})`;
        const text =
          s.change_pct >= 0 ? "text-tertiary-fixed-dim" : "text-cyber-red";

        return (
          <div
            key={s.symbol}
            className="p-2 text-center border border-border-glow/50"
            style={{ background: bg }}
          >
            <p className="font-mono text-[10px] font-bold tracking-[0.1em] uppercase text-text-muted truncate">
              {s.name}
            </p>
            <p className={`tabular-nums font-mono text-sm font-bold ${text}`}>
              {s.change_pct >= 0 ? "+" : ""}
              {s.change_pct.toFixed(2)}%
            </p>
          </div>
        );
      })}
    </div>
  );
}
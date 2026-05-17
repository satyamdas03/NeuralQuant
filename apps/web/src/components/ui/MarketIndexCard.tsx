import type { IndexData } from "@/lib/types";

type Props = {
  index: IndexData;
};

export default function MarketIndexCard({ index }: Props) {
  const up = index.change_pct >= 0;

  return (
    <div className="flex items-center justify-between glass border border-border-glow px-3 py-2">
      <div>
        <p className="font-mono text-[10px] font-bold tracking-[0.2em] uppercase text-text-muted">
          {index.name}
        </p>
        <p className="tabular-nums font-mono text-sm font-bold text-primary">
          {index.price.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
        </p>
      </div>
      <span
        className={`tabular-nums font-mono text-[11px] font-bold ${
          up ? "text-tertiary-fixed-dim" : "text-cyber-red"
        }`}
      >
        {up ? "+" : ""}
        {index.change_pct.toFixed(2)}%
      </span>
    </div>
  );
}

import type { IndexData } from "@/lib/types";

type Props = {
  index: IndexData;
};

export default function MarketIndexCard({ index }: Props) {
  const up = index.change_pct >= 0;

  return (
    <div className="flex items-center justify-between rounded-lg bg-surface-container px-3 py-2 ghost-border">
      <div>
        <p className="text-xs font-medium text-on-surface-variant">
          {index.name}
        </p>
        <p className="tabular-nums text-sm font-semibold text-on-surface">
          {index.price.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
        </p>
      </div>
      <span
        className={`tabular-nums text-xs font-medium ${
          up ? "text-tertiary" : "text-error"
        }`}
      >
        {up ? "+" : ""}
        {index.change_pct.toFixed(2)}%
      </span>
    </div>
  );
}
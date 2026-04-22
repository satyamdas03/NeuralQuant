import type { AIScore } from "@/lib/types";
import RegimeBadge from "./RegimeBadge";

type Props = {
  stock: AIScore;
  onClick: (ticker: string) => void;
  currency?: string;
};

export default function ScreenerCard({
  stock,
  onClick,
  currency = "$",
}: Props) {
  const scoreColor =
    stock.score_1_10 >= 7
      ? "text-tertiary"
      : stock.score_1_10 >= 4
      ? "text-primary"
      : "text-error";

  return (
    <div
      onClick={() => onClick(stock.ticker)}
      className="cursor-pointer rounded-xl bg-surface-container ghost-border p-4 hover-glow transition-shadow"
    >
      <div className="flex items-center justify-between">
        <span className="font-headline font-bold text-on-surface">
          {stock.ticker}
        </span>
        <RegimeBadge regime={stock.regime_label} />
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className={`tabular-nums text-2xl font-bold ${scoreColor}`}>
          {stock.score_1_10.toFixed(1)}
        </span>
        <span className="text-xs text-on-surface-variant">/10</span>
      </div>
      <div className="mt-2 text-xs text-on-surface-variant capitalize">
        {stock.confidence} confidence
      </div>
    </div>
  );
}
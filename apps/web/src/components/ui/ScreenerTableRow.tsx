import type { AIScore } from "@/lib/types";
import RegimeBadge from "./RegimeBadge";

type Props = {
  stock: AIScore;
  onClick: (ticker: string) => void;
  currency?: string;
};

export default function ScreenerTableRow({
  stock,
  onClick,
  currency = "$",
}: Props) {
  return (
    <tr
      onClick={() => onClick(stock.ticker)}
      className="cursor-pointer hover:bg-surface-high transition-colors"
    >
      <td className="py-3 pr-4">
        <div>
          <span className="font-semibold text-on-surface">
            {stock.ticker}
          </span>
        </div>
      </td>
      <td className="py-3 pr-4">
        <span
          className={`tabular-nums font-bold ${
            stock.score_1_10 >= 7
              ? "text-tertiary"
              : stock.score_1_10 >= 4
              ? "text-primary"
              : "text-error"
          }`}
        >
          {stock.score_1_10.toFixed(1)}
        </span>
      </td>
      <td className="py-3 pr-4">
        <RegimeBadge regime={stock.regime_label} />
      </td>
      <td className="py-3">
        <span className="text-xs text-on-surface-variant">
          {stock.confidence}
        </span>
      </td>
    </tr>
  );
}
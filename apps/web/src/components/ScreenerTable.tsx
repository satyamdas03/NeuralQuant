import Link from "next/link";
import type { AIScore } from "@/lib/types";
import RegimeBadge from "@/components/ui/RegimeBadge";

export function ScreenerTable({ stocks }: { stocks: AIScore[] }) {
  return (
    <div className="overflow-hidden rounded-2xl ghost-border">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-surface-low text-on-surface-variant text-xs uppercase tracking-wider">
            <tr>
              <th className="px-4 py-3 text-left">Ticker</th>
              <th className="px-4 py-3 text-center">AI Score</th>
              <th className="px-4 py-3 text-center">Quality</th>
              <th className="px-4 py-3 text-center">Momentum</th>
              <th className="px-4 py-3 text-center">Regime</th>
              <th className="px-4 py-3 text-center">Confidence</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ghost-border/50">
            {stocks.map((s, i) => (
              <tr key={s.ticker} className="hover:bg-surface-high transition-colors">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <span className="w-5 text-xs text-on-surface-variant">{i + 1}</span>
                    <Link
                      href={`/stocks/${s.ticker}?market=${s.market}`}
                      className="font-semibold text-on-surface hover:text-primary transition-colors"
                    >
                      {s.ticker}
                    </Link>
                    <span className="text-xs text-on-surface-variant">{s.market}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-center">
                  <span
                    className={`text-lg font-bold ${
                      s.score_1_10 >= 7
                        ? "text-tertiary"
                        : s.score_1_10 >= 4
                        ? "text-primary"
                        : "text-error"
                    }`}
                  >
                    {s.score_1_10}
                  </span>
                  <span className="text-xs text-on-surface-variant">/10</span>
                </td>
                <td className="px-4 py-3 text-center tabular-nums text-on-surface">
                  {(s.sub_scores.quality * 100).toFixed(0)}%
                </td>
                <td className="px-4 py-3 text-center tabular-nums text-on-surface">
                  {(s.sub_scores.momentum * 100).toFixed(0)}%
                </td>
                <td className="px-4 py-3 text-center">
                  <RegimeBadge regime={s.regime_label} />
                </td>
                <td className="px-4 py-3 text-center">
                  <span
                    className={`text-xs capitalize ${
                      s.confidence === "high"
                        ? "text-tertiary"
                        : s.confidence === "medium"
                        ? "text-primary"
                        : "text-error"
                    }`}
                  >
                    {s.confidence}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
import Link from "next/link";
import type { AIScore } from "@/lib/types";
import RegimeBadge from "@/components/ui/RegimeBadge";

/** Anjali composite → color class. Scale: -16 to +16 */
function anjaliColorClass(composite: number | null | undefined): string {
  if (composite == null) return "text-on-surface-variant";
  if (composite >= 6) return "text-tertiary-fixed-dim";   // strong value
  if (composite >= 2) return "text-primary-fixed";        // moderate value
  if (composite >= -2) return "text-on-surface-variant";  // neutral
  return "text-cyber-red";                                  // bearish
}

/** Anjali composite → short label */
function anjaliLabel(composite: number | null | undefined): string {
  if (composite == null) return "—";
  return composite >= 0 ? `+${composite.toFixed(1)}` : composite.toFixed(1);
}

export function ScreenerTable({ stocks }: { stocks: AIScore[] }) {
  // Check if ANY stock has Anjali data (to conditionally show column)
  const hasAnjali = stocks.some((s) => s.anjali != null);

  return (
    <div className="overflow-hidden glass border border-border-glow">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-surface-container-low text-text-muted font-mono text-[10px] font-bold tracking-[0.2em] uppercase">
            <tr>
              <th className="px-4 py-3 text-left">Ticker</th>
              <th className="px-4 py-3 text-center">Score</th>
              {hasAnjali && <th className="px-4 py-3 text-center">Anjali</th>}
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
                  <div className="flex items-center gap-2">
                    <span className="w-5 text-xs text-on-surface-variant">{i + 1}</span>
                    <Link
                      href={`/stocks/${s.ticker}?market=${s.market}`}
                      className="font-semibold text-on-surface hover:text-primary transition-colors"
                    >
                      {s.ticker}
                    </Link>
                    {s.anjali?.is_loss_making && (
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-error/15 text-error border border-error/30">
                        LOSS
                      </span>
                    )}
                    {s.anjali?.valuation_sweet_spot && (
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-tertiary/15 text-tertiary border border-tertiary/30">
                        VALUE
                      </span>
                    )}
                    <span className="text-xs text-on-surface-variant">{s.market}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-center">
                  <span
                    className={`font-mono text-lg font-bold ${
                      s.score_1_10 >= 7
                        ? "text-tertiary-fixed-dim"
                        : s.score_1_10 >= 4
                        ? "text-primary-fixed"
                        : "text-cyber-red"
                    }`}
                  >
                    {s.score_1_10}
                  </span>
                  <span className="font-mono text-[11px] text-text-muted">/10</span>
                </td>
                {hasAnjali && (
                  <td className="px-4 py-3 text-center">
                    <span className={`font-mono font-semibold ${anjaliColorClass(s.anjali?.composite)}`}>
                      {anjaliLabel(s.anjali?.composite)}
                    </span>
                  </td>
                )}
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
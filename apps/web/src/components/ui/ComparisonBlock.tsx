import type { ComparisonItem } from "@/lib/types";

type Props = { comparisons: ComparisonItem[] };

export default function ComparisonBlock({ comparisons }: Props) {
  if (!comparisons.length) return null;
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-on-surface-variant uppercase tracking-wide">Head-to-Head</p>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-surface-container">
              <th className="text-left py-1 text-on-surface-variant font-medium">Metric</th>
              <th className="text-right py-1 text-emerald-400 font-medium">Ours</th>
              <th className="text-right py-1 text-red-400 font-medium">Theirs</th>
              <th className="text-left py-1 text-primary font-medium pl-3">Edge</th>
            </tr>
          </thead>
          <tbody>
            {comparisons.map((c, i) => (
              <tr key={i} className="border-b border-surface-container/50">
                <td className="py-1.5 text-on-surface-variant">{c.metric}</td>
                <td className="py-1.5 text-right font-medium text-on-surface">{c.ours}</td>
                <td className="py-1.5 text-right text-on-surface-variant">{c.theirs}</td>
                <td className="py-1.5 pl-3 text-primary">{c.edge}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
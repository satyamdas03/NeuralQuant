import Link from "next/link";
import type { AIScore } from "@/lib/types";
import { RegimeBadge } from "./RegimeBadge";

export function ScreenerTable({ stocks }: { stocks: AIScore[] }) {
  return (
    <div className="rounded-2xl border border-gray-800 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-900/80 text-gray-500 text-xs uppercase tracking-wider">
          <tr>
            <th className="px-4 py-3 text-left">Ticker</th>
            <th className="px-4 py-3 text-center">AI Score</th>
            <th className="px-4 py-3 text-center">Quality</th>
            <th className="px-4 py-3 text-center">Momentum</th>
            <th className="px-4 py-3 text-center">Regime</th>
            <th className="px-4 py-3 text-center">Confidence</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800">
          {stocks.map((s, i) => (
            <tr key={s.ticker} className="hover:bg-gray-900/50 transition-colors">
              <td className="px-4 py-3">
                <div className="flex items-center gap-3">
                  <span className="text-gray-600 text-xs w-5">{i + 1}</span>
                  <Link
                    href={`/stocks/${s.ticker}`}
                    className="font-semibold text-white hover:text-violet-400 transition-colors"
                  >
                    {s.ticker}
                  </Link>
                  <span className="text-xs text-gray-500">{s.market}</span>
                </div>
              </td>
              <td className="px-4 py-3 text-center">
                <span className={`font-bold text-lg ${
                  s.score_1_10 >= 7 ? "text-green-400" :
                  s.score_1_10 >= 4 ? "text-yellow-400" : "text-red-400"
                }`}>{s.score_1_10}</span>
                <span className="text-gray-600 text-xs">/10</span>
              </td>
              <td className="px-4 py-3 text-center text-gray-300">
                {(s.sub_scores.quality * 100).toFixed(0)}%
              </td>
              <td className="px-4 py-3 text-center text-gray-300">
                {(s.sub_scores.momentum * 100).toFixed(0)}%
              </td>
              <td className="px-4 py-3 text-center">
                <RegimeBadge label={s.regime_label} />
              </td>
              <td className="px-4 py-3 text-center">
                <span className={`text-xs ${
                  s.confidence === "high" ? "text-green-400" :
                  s.confidence === "medium" ? "text-yellow-400" : "text-red-400"
                }`}>{s.confidence}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

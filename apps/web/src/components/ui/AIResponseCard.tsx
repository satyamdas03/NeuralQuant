import RegimeBadge from "./RegimeBadge";
import type { RegimeLabel } from "@/lib/types";

type Props = {
  answer: string;
  sources?: string[];
  regime?: RegimeLabel;
  score?: number;
};

export default function AIResponseCard({
  answer,
  sources = [],
  regime,
  score,
}: Props) {
  return (
    <div className="rounded-xl bg-surface-container ghost-border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-secondary">NeuralQuant ForeCast</span>
        <div className="flex items-center gap-2">
          {regime && <RegimeBadge regime={regime} />}
          {score !== undefined && (
            <span className="tabular-nums text-xs text-on-surface-variant">
              ForeCast: {score.toFixed(1)}/10
            </span>
          )}
        </div>
      </div>
      <div className="text-sm text-on-surface leading-relaxed whitespace-pre-wrap">
        {answer}
      </div>
      {sources.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {sources.map((s, i) => (
            <span
              key={i}
              className="rounded-full bg-surface-high px-2 py-0.5 text-[10px] text-on-surface-variant"
            >
              {s}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
import RegimeBadge from "./RegimeBadge";
import VerdictBanner from "./VerdictBanner";
import MetricsGrid from "./MetricsGrid";
import ReasoningBlock from "./ReasoningBlock";
import ScenarioBar from "./ScenarioBar";
import AllocationTable from "./AllocationTable";
import ComparisonBlock from "./ComparisonBlock";
import type { RegimeLabel, StructuredQueryResponse } from "@/lib/types";

type Props = {
  answer: string;
  sources?: string[];
  regime?: RegimeLabel;
  score?: number;
  structured?: StructuredQueryResponse | null;
};

function tryParseStructured(answer: string): StructuredQueryResponse | null {
  try {
    const match = answer.match(/\{[\s\S]*"verdict"[\s\S]*\}/);
    if (match) {
      const data = JSON.parse(match[0]);
      if (data.verdict && data.summary) return data as StructuredQueryResponse;
    }
  } catch {}
  return null;
}

export default function AIResponseCard({
  answer,
  sources = [],
  regime,
  score,
  structured,
}: Props) {
  const parsed = structured ?? tryParseStructured(answer);

  if (parsed) {
    return (
      <div className="rounded-xl bg-surface-container ghost-border p-4 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-secondary">NeuralQuant ForeCast</span>
          <span className="text-[10px] text-on-surface-variant uppercase">{parsed.route}</span>
        </div>

        <VerdictBanner
          verdict={parsed.verdict}
          confidence={parsed.confidence}
          timeframe={parsed.timeframe}
        />

        <p className="text-sm text-on-surface leading-relaxed">{parsed.summary}</p>

        <MetricsGrid metrics={parsed.metrics} />
        <ReasoningBlock reasoning={parsed.reasoning} />
        <ScenarioBar scenarios={parsed.scenarios} />
        <AllocationTable allocations={parsed.allocations} />
        <ComparisonBlock comparisons={parsed.comparisons} />

        {parsed.data_sources.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {parsed.data_sources.map((s, i) => (
              <span key={i} className="rounded-full bg-surface-high px-2 py-0.5 text-[10px] text-on-surface-variant">{s}</span>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Fallback: freeform text rendering (existing behavior)
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
            <span key={i} className="rounded-full bg-surface-high px-2 py-0.5 text-[10px] text-on-surface-variant">{s}</span>
          ))}
        </div>
      )}
    </div>
  );
}
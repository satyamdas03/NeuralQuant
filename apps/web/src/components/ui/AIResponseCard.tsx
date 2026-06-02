import RegimeBadge from "./RegimeBadge";
import VerdictBanner from "./VerdictBanner";
import MetricsGrid from "./MetricsGrid";
import ReasoningBlock from "./ReasoningBlock";
import ScenarioBar from "./ScenarioBar";
import AllocationTable from "./AllocationTable";
import ComparisonBlock from "./ComparisonBlock";
import StockSummaryCard from "./StockSummaryCard";
import MarketContextStrip from "./MarketContextStrip";
import AllocationBar from "./AllocationBar";
import PortfolioStockCard from "./PortfolioStockCard";
import ScenarioAnalysisPanel from "./ScenarioAnalysisPanel";
import ActionPromptButtons from "./ActionPromptButtons";
import SEBIDisclaimer from "./SEBIDisclaimer";
import type { RegimeLabel, StructuredQueryResponse } from "@/lib/types";
import ProfilerCard from "./ProfilerCard";
import ClarificationCard from "./ClarificationCard";
import MorganReportCard from "@/components/MorganReportCard";
import type { UserProfile } from "@/lib/types";

type Props = {
  answer: string;
  sources?: string[];
  regime?: RegimeLabel;
  score?: number;
  structured?: StructuredQueryResponse | null;
  hideVerdict?: boolean;
  onFollowUp?: (text: string) => void;
  onProfilerSubmit?: (profile: UserProfile) => void;
  onClarificationSubmit?: (answers: string[]) => void;
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
  hideVerdict = false,
  onFollowUp,
  onProfilerSubmit,
  onClarificationSubmit,
}: Props) {
  const parsed = structured ?? tryParseStructured(answer);

  if (parsed) {
    if (parsed.clarification_needed && parsed.clarification_questions?.length) {
      return (
        <ClarificationCard
          questions={parsed.clarification_questions}
          context={parsed.clarification_context}
          onSubmit={onClarificationSubmit || (() => {})}
        />
      );
    }
    if (parsed.profiler_needed) {
      let savedAmount: string | undefined;
      try {
        const guest = typeof window !== "undefined" ? localStorage.getItem("nq_profile") : null;
        const parsedGuest = guest ? JSON.parse(guest) : null;
        savedAmount = parsedGuest?.investable_amount;
      } catch {}
      return (
        <ProfilerCard
          defaultAmount={savedAmount}
          onSubmit={onProfilerSubmit || (() => {})}
        />
      );
    }
    if (parsed.is_report) {
      return <MorganReportCard response={parsed} />;
    }
    if (parsed.is_portfolio_response) {
      return (
        <div className="bg-surface-container ghost-border p-4 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-primary-fixed">QuantAlpha Portfolio ForeCast</span>
            <span className="text-[10px] text-on-surface-variant uppercase">{parsed.route}</span>
          </div>

          <MarketContextStrip cards={parsed.market_context ?? []} />
          <AllocationBar segments={parsed.allocation_breakdown ?? []} />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {(parsed.portfolio_stocks ?? []).map((s) => (
              <PortfolioStockCard key={s.ticker} stock={s} />
            ))}
          </div>

          <ScenarioAnalysisPanel scenarios={parsed.scenario_analysis ?? []} />

          {onFollowUp && (
            <ActionPromptButtons
              prompts={parsed.action_prompts ?? []}
              onPromptClick={onFollowUp}
            />
          )}

          <SEBIDisclaimer
            text={
              parsed.sebi_disclaimer ??
              "This is AI-generated investment research, not SEBI-registered investment advice. Please consult a certified financial advisor before investing."
            }
          />

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

    return (
      <div className="bg-surface-container ghost-border p-4 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-primary-fixed">QuantAlpha ForeCast</span>
          <span className="text-[10px] text-on-surface-variant uppercase">{parsed.route}</span>
        </div>

        {parsed.stock_summary && (
          <StockSummaryCard summary={parsed.stock_summary} />
        )}

        {!hideVerdict && (
          <VerdictBanner
            verdict={parsed.verdict}
            confidence={parsed.confidence}
            timeframe={parsed.timeframe}
          />
        )}

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
    <div className="bg-surface-container ghost-border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-primary-fixed">QuantAlpha ForeCast</span>
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
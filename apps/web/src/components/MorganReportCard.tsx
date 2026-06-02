"use client";

import type { StructuredQueryResponse } from "@/lib/types";
import StockSummaryCard from "@/components/ui/StockSummaryCard";
import VerdictBanner from "@/components/ui/VerdictBanner";
import MetricsGrid from "@/components/ui/MetricsGrid";
import ReasoningBlock from "@/components/ui/ReasoningBlock";
import ScenarioBar from "@/components/ui/ScenarioBar";
import AllocationTable from "@/components/ui/AllocationTable";
import ComparisonBlock from "@/components/ui/ComparisonBlock";
import SEBIDisclaimer from "@/components/ui/SEBIDisclaimer";

interface MorganReportCardProps {
  response: StructuredQueryResponse;
}

/**
 * Renders a Morgan Institutional Research Report — formal 16-section format
 * triggered when is_report=true in the structured query response.
 */
export default function MorganReportCard({ response }: MorganReportCardProps) {
  return (
    <div className="bg-surface-container ghost-border p-5 space-y-5">
      {/* Report Header */}
      <div className="flex items-center justify-between border-b border-amber-500/30 pb-3">
        <div className="flex items-center gap-2.5">
          <span className="text-lg">📊</span>
          <div>
            <span className="text-xs font-mono font-bold uppercase tracking-[0.15em] text-amber-400">
              Morgan Institutional Report
            </span>
            <span className="block text-[9px] font-mono text-on-surface-variant mt-0.5">
              {response.route} · Institutional-Grade Research
            </span>
          </div>
        </div>
        <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30 uppercase tracking-wider">
          Report
        </span>
      </div>

      {/* Stock Summary */}
      {response.stock_summary && (
        <StockSummaryCard summary={response.stock_summary} />
      )}

      {/* Verdict */}
      <VerdictBanner verdict={response.verdict} confidence={response.confidence} timeframe={response.timeframe} />

      {/* Executive Summary */}
      <div className="space-y-1.5">
        <h3 className="text-[10px] font-mono uppercase tracking-wider text-amber-400/80">Executive Summary</h3>
        <p className="text-sm text-on-surface leading-relaxed">{response.summary}</p>
      </div>

      {/* Key Metrics */}
      {response.metrics.length > 0 && <MetricsGrid metrics={response.metrics} />}

      {/* Investment Thesis / Reasoning */}
      {response.reasoning && <ReasoningBlock reasoning={response.reasoning} />}

      {/* Scenarios */}
      {response.scenarios.length > 0 && <ScenarioBar scenarios={response.scenarios} />}

      {/* Portfolio Allocation */}
      {response.allocations.length > 0 && <AllocationTable allocations={response.allocations} />}

      {/* Comparisons */}
      {response.comparisons.length > 0 && <ComparisonBlock comparisons={response.comparisons} />}

      {/* Data Sources */}
      {response.data_sources.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {response.data_sources.map((s, i) => (
            <span key={i} className="rounded-full bg-surface-high px-2 py-0.5 text-[10px] text-on-surface-variant">{s}</span>
          ))}
        </div>
      )}

      {/* Follow-up Questions */}
      {response.follow_up_questions.length > 0 && (
        <div className="space-y-1.5 pt-2 border-t border-outline-variant/20">
          <span className="text-[10px] font-mono uppercase tracking-wider text-on-surface-variant">Continue Research</span>
          <ul className="space-y-1">
            {response.follow_up_questions.slice(0, 3).map((q, i) => (
              <li key={i} className="text-xs text-on-surface-variant hover:text-primary transition-colors cursor-pointer">
                → {q}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* SEBI Disclaimer */}
      <SEBIDisclaimer
        text={
          response.sebi_disclaimer ??
          "This is AI-generated institutional research, not SEBI-registered investment advice. Please consult a certified financial advisor before investing."
        }
      />
    </div>
  );
}
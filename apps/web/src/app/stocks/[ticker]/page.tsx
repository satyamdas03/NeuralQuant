"use client";
import { useEffect, useState, use } from "react";
import { api } from "@/lib/api";
import type { AIScore, AnalystResponse } from "@/lib/types";
import { AIScoreCard } from "@/components/AIScoreCard";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import { FeatureAttribution } from "@/components/FeatureAttribution";
import { AgentDebatePanel } from "@/components/AgentDebatePanel";

export default function StockPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = use(params);
  const [score, setScore] = useState<AIScore | null>(null);
  const [report, setReport] = useState<AnalystResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [analysing, setAnalysing] = useState(false);

  useEffect(() => {
    api.getStock(ticker).then(setScore).finally(() => setLoading(false));
  }, [ticker]);

  const runDebate = async () => {
    setAnalysing(true);
    try {
      const r = await api.runAnalyst({ ticker });
      setReport(r);
    } finally {
      setAnalysing(false);
    }
  };

  if (loading) return <div className="text-gray-500 animate-pulse">Loading AI score...</div>;
  if (!score) return <div className="text-red-400">Stock not found: {ticker}</div>;

  return (
    <div className="space-y-6">
      <div className="grid md:grid-cols-3 gap-6">
        <AIScoreCard data={score} />
        <ScoreBreakdown scores={score.sub_scores} />
        <FeatureAttribution drivers={score.top_drivers} />
      </div>

      {!report ? (
        <div className="text-center py-12">
          <button
            onClick={runDebate}
            disabled={analysing}
            className="px-8 py-4 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 rounded-xl text-white font-semibold transition-colors"
          >
            {analysing ? "7 analysts debating..." : "Run PARA-DEBATE Analysis"}
          </button>
          <p className="text-gray-500 text-sm mt-2">
            Runs 7 Claude AI analysts in parallel (~5-10 seconds)
          </p>
        </div>
      ) : (
        <AgentDebatePanel report={report} />
      )}
    </div>
  );
}

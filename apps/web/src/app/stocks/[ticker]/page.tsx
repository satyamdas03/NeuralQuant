"use client";
import { useEffect, useState, use } from "react";
import { api } from "@/lib/api";
import type { AIScore, AnalystResponse, StockMeta, Market } from "@/lib/types";
import { AIScoreCard } from "@/components/AIScoreCard";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import { FeatureAttribution } from "@/components/FeatureAttribution";
import { AgentDebatePanel } from "@/components/AgentDebatePanel";
import { PriceChart } from "@/components/PriceChart";
import { StockMetaBar } from "@/components/StockMetaBar";
import { toggleWatchlist, isWatchlisted } from "@/lib/watchlist";

export default function StockPage({
  params,
  searchParams,
}: {
  params: Promise<{ ticker: string }>;
  searchParams: Promise<{ market?: string }>;
}) {
  const { ticker } = use(params);
  const { market: marketParam } = use(searchParams);
  const market = (marketParam ?? "US") as Market;

  const [score, setScore] = useState<AIScore | null>(null);
  const [meta, setMeta] = useState<StockMeta | null>(null);
  const [report, setReport] = useState<AnalystResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [analysing, setAnalysing] = useState(false);
  const [watchlisted, setWatchlisted] = useState(false);

  useEffect(() => {
    setWatchlisted(isWatchlisted(ticker.toUpperCase()));
    api.getStock(ticker, market).then(setScore).finally(() => setLoading(false));
    api.getStockMeta(ticker, market).then(setMeta).catch(() => {});
  }, [ticker, market]);

  const runDebate = async () => {
    setAnalysing(true);
    try {
      const r = await api.runAnalyst({ ticker, market });
      setReport(r);
    } finally {
      setAnalysing(false);
    }
  };

  const handleWatchlist = () => {
    const now = toggleWatchlist(ticker.toUpperCase());
    setWatchlisted(now);
  };

  if (loading)
    return <div className="text-gray-500 animate-pulse py-12 text-center">Loading AI score…</div>;
  if (!score)
    return <div className="text-red-400 py-12 text-center">Stock not found: {ticker}</div>;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">{ticker.toUpperCase()}</h1>
          {meta?.name && ticker.toUpperCase() !== meta.name && (
            <p className="text-sm text-gray-400 mt-0.5">{meta.name}</p>
          )}
          {meta?.sector && (
            <p className="text-xs text-gray-500 mt-0.5">{meta.sector} · {meta.industry}</p>
          )}
        </div>
        <button
          onClick={handleWatchlist}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-colors ${
            watchlisted
              ? "border-yellow-500/40 bg-yellow-500/10 text-yellow-400"
              : "border-gray-700 text-gray-400 hover:text-white hover:border-gray-600"
          }`}
        >
          {watchlisted ? "★ Watching" : "☆ Watchlist"}
        </button>
      </div>

      {/* AI Score Cards */}
      <div className="grid md:grid-cols-3 gap-5">
        <AIScoreCard data={score} />
        <ScoreBreakdown scores={score.sub_scores} />
        <FeatureAttribution drivers={score.top_drivers} />
      </div>

      {/* Meta bar (fundamentals overview) */}
      {meta && <StockMetaBar meta={meta} />}

      {/* Price Chart */}
      <PriceChart ticker={ticker.toUpperCase()} market={market} />

      {/* PARA-DEBATE */}
      {!report ? (
        <div className="text-center py-10">
          <button
            onClick={runDebate}
            disabled={analysing}
            className="px-8 py-4 bg-gradient-to-r from-violet-600 to-cyan-600 hover:from-violet-500 hover:to-cyan-500 disabled:opacity-50 rounded-xl text-white font-semibold transition-all shadow-lg hover:shadow-violet-500/20"
          >
            {analysing ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                7 analysts debating…
              </span>
            ) : (
              "Run PARA-DEBATE Analysis"
            )}
          </button>
          <p className="text-gray-500 text-sm mt-2">
            7 Claude AI analysts debate the stock in parallel (~5–10 s)
          </p>
        </div>
      ) : (
        <AgentDebatePanel report={report} />
      )}
    </div>
  );
}

"use client";
import { useEffect, useState, use } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
import type { AIScore, AnalystResponse, StockMeta, Market, SentimentResponse } from "@/lib/types";
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
  const [sentiment, setSentiment] = useState<SentimentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [analysing, setAnalysing] = useState(false);
  const [watchlisted, setWatchlisted] = useState(false);

  useEffect(() => {
    setWatchlisted(isWatchlisted(ticker.toUpperCase()));
    api.getStock(ticker, market).then(setScore).finally(() => setLoading(false));
    api.getStockMeta(ticker, market).then(setMeta).catch(() => {});
    api.getSentiment(ticker, market, 12).then(setSentiment).catch(() => {});
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
      {meta && <StockMetaBar meta={meta} market={market} />}

      {/* Price Chart */}
      <PriceChart ticker={ticker.toUpperCase()} market={market} />

      {/* Sentiment + Backtest row */}
      <div className="grid md:grid-cols-2 gap-5">
        <SentimentCard s={sentiment} ticker={ticker.toUpperCase()} />
        <BacktestCTA ticker={ticker.toUpperCase()} market={market} />
      </div>

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

function SentimentCard({ s, ticker }: { s: SentimentResponse | null; ticker: string }) {
  const color =
    !s ? "text-gray-400"
    : s.label === "Bullish" ? "text-emerald-400"
    : s.label === "Bearish" ? "text-red-400"
    : "text-yellow-400";
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-sm text-gray-300 uppercase tracking-wide">News Sentiment</h3>
        <span className="text-xs text-gray-500">VADER · {s?.n_headlines ?? 0} headlines</span>
      </div>
      {!s ? (
        <div className="text-sm text-gray-500">Loading…</div>
      ) : s.n_headlines === 0 ? (
        <div className="text-sm text-gray-500">No recent headlines for {ticker}.</div>
      ) : (
        <>
          <div className="flex items-baseline gap-3">
            <span className={`text-3xl font-bold ${color}`}>{s.label}</span>
            <span className="text-sm text-gray-500 tabular-nums">
              {s.aggregate_score >= 0 ? "+" : ""}{s.aggregate_score.toFixed(2)}
            </span>
          </div>
          <div className="mt-4 space-y-1.5 max-h-56 overflow-y-auto pr-1">
            {s.headlines.slice(0, 6).map((h, i) => (
              <a
                key={i}
                href={h.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-start justify-between gap-3 text-xs text-gray-400 hover:text-white"
              >
                <span className="leading-snug line-clamp-2">{h.title}</span>
                <span
                  className={`shrink-0 tabular-nums ${
                    h.score > 0 ? "text-emerald-400" : h.score < 0 ? "text-red-400" : "text-gray-500"
                  }`}
                >
                  {h.score >= 0 ? "+" : ""}{h.score.toFixed(2)}
                </span>
              </a>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function BacktestCTA({ ticker, market }: { ticker: string; market: Market }) {
  return (
    <div className="bg-gradient-to-br from-violet-600/10 to-cyan-600/10 border border-violet-500/20 rounded-xl p-5 flex flex-col justify-between">
      <div>
        <h3 className="font-semibold text-sm text-gray-300 uppercase tracking-wide">Strategy Backtest</h3>
        <p className="text-sm text-gray-400 mt-2 leading-relaxed">
          Test a moving-average crossover on {ticker} — see Sharpe, max drawdown, and how it compares to buy-and-hold.
        </p>
      </div>
      <Link
        href={`/backtest?ticker=${ticker}&market=${market}`}
        className="mt-4 inline-block px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium w-fit transition-colors"
      >
        Run backtest →
      </Link>
    </div>
  );
}

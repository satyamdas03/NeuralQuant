"use client";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { api, authedApi } from "@/lib/api";
import Link from "next/link";
import type { AIScore, AnalystResponse, StockMeta, Market, SentimentResponse } from "@/lib/types";
import { AIScoreCard } from "@/components/AIScoreCard";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import { FeatureAttribution } from "@/components/FeatureAttribution";
import { AgentDebatePanel } from "@/components/AgentDebatePanel";
import { PriceChart } from "@/components/PriceChart";
import { StockMetaBar } from "@/components/StockMetaBar";
import { RegimeContextPanel } from "@/components/RegimeContextPanel";
import { TransparencyPanel } from "@/components/TransparencyPanel";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import GradientButton from "@/components/ui/GradientButton";
import GlassPanel from "@/components/ui/GlassPanel";
import { Star, ArrowRight, Loader2 } from "lucide-react";

export default function StockPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const ticker = (params.ticker as string) ?? "";
  const market = (searchParams.get("market") ?? "US") as Market;

  const [score, setScore] = useState<AIScore | null>(null);
  const [meta, setMeta] = useState<StockMeta | null>(null);
  const [report, setReport] = useState<AnalystResponse | null>(null);
  const [sentiment, setSentiment] = useState<SentimentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [analysing, setAnalysing] = useState(false);
  const [watchlisted, setWatchlisted] = useState(false);

  useEffect(() => {
    api.getStock(ticker, market).then(setScore).catch((e) => console.error("getStock failed:", e)).finally(() => setLoading(false));
    api.getStockMeta(ticker, market).then(setMeta).catch(() => {});
    api.getSentiment(ticker, market, 12).then(setSentiment).catch(() => {});
    authedApi.listWatchlist().then(r => {
      setWatchlisted(r.items.some(i => i.ticker === ticker.toUpperCase()));
    }).catch(() => {}); // Not logged in — non-critical
  }, [ticker, market]);

  // Live score updates via SSE — route through Next.js /api proxy to avoid CORS.
  // Next.js rewrites don't support SSE, so we use a dedicated API route.
  useEffect(() => {
    const url = `/api/stocks/${ticker}/stream?market=${market}`;
    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      const es = new EventSource(url);
      es.addEventListener("score", (e) => {
        try { setScore(JSON.parse(e.data)); } catch { /* ignore bad data */ }
      });
      es.addEventListener("error", () => { es.close(); });
    };

    // SSE through Next.js rewrites is unreliable (proxy buffering).
    // Fallback: poll every 30s for live score via REST.
    const poll = async () => {
      if (cancelled) return;
      try {
        const s = await api.getStock(ticker, market);
        if (!cancelled) setScore(s);
      } catch { /* ignore */ }
    };
    poll();
    const interval = setInterval(poll, 30_000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [ticker, market]);

  const runDebate = async () => {
    // Check auth first
    try {
      const { createClient } = await import("@/lib/supabase/client");
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      if (!data.session?.access_token) {
        setReport({ ticker: ticker.toUpperCase(), market, debate: [], consensus: "", verdict: "Sign in required to run PARA-DEBATE." } as any);
        return;
      }
    } catch { /* proceed */ }

    setAnalysing(true);
    try {
      const r = await api.runAnalyst({ ticker, market });
      setReport(r);
    } finally {
      setAnalysing(false);
    }
  };

  const handleWatchlist = async () => {
    try {
      if (watchlisted) {
        const r = await authedApi.listWatchlist();
        const item = r.items.find(i => i.ticker === ticker.toUpperCase());
        if (item) await authedApi.deleteWatchlist(item.id);
        setWatchlisted(false);
      } else {
        await authedApi.addWatchlist({ ticker: ticker.toUpperCase(), market: market === "IN" ? "IN" : "US" });
        setWatchlisted(true);
      }
    } catch {
      // silently fail — non-critical
    }
  };

  if (loading) return <StockPageSkeleton ticker={ticker.toUpperCase()} />;
  if (!score)
    return <div className="text-error py-12 text-center">Stock not found: {ticker}</div>;

  return (
    <div className="space-y-5 p-4 lg:p-6">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "FinancialProduct",
            name: ticker,
            description: `NeuralQuant AI analysis for ${ticker}`,
            url: `https://neuralquant.vercel.app/stocks/${ticker}`,
          }),
        }}
      />
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-headline text-2xl font-bold text-on-surface">{ticker.toUpperCase()}</h1>
          {meta?.name && ticker.toUpperCase() !== meta.name && (
            <p className="text-sm text-on-surface-variant mt-0.5">{meta.name}</p>
          )}
          {meta?.sector && (
            <p className="text-xs text-on-surface-variant mt-0.5">{meta.sector} · {meta.industry}</p>
          )}
        </div>
        <button
          onClick={handleWatchlist}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            watchlisted
              ? "ghost-border bg-primary/10 text-primary"
              : "ghost-border text-on-surface-variant hover:text-on-surface hover:bg-surface-high"
          }`}
        >
          <Star size={14} className={watchlisted ? "fill-primary" : ""} />
          {watchlisted ? "Watching" : "Watchlist"}
        </button>
      </div>

      {/* Regime Context */}
      <RegimeContextPanel regime={score.regime_label} />

      {/* ForeCast Score Cards */}
      <div className="grid md:grid-cols-3 gap-5">
        <AIScoreCard data={score} />
        <ScoreBreakdown scores={score.sub_scores} />
        <FeatureAttribution drivers={score.top_drivers} />
      </div>

      {/* Transparency Layer */}
      <TransparencyPanel score={score} report={report} />

      {/* Meta bar */}
      {meta && <StockMetaBar meta={meta} market={market} />}

      {/* Price Chart */}
      <PriceChart ticker={ticker.toUpperCase()} market={market} />

      {/* Sentiment + Backtest row */}
      <div className="grid md:grid-cols-2 gap-5">
        <SentimentCard s={sentiment} ticker={ticker.toUpperCase()} market={market} />
        <BacktestCTA ticker={ticker.toUpperCase()} market={market} />
      </div>

      {/* PARA-DEBATE */}
      {!report ? (
        <div className="text-center py-10">
          <GradientButton onClick={runDebate} disabled={analysing} size="md">
            {analysing ? (
              <span className="flex items-center gap-2">
                <Loader2 size={16} className="animate-spin" />
                7 analysts debating…
              </span>
            ) : (
              "Run PARA-DEBATE Analysis"
            )}
          </GradientButton>
          <p className="text-on-surface-variant text-sm mt-2">
            7 Claude AI analysts debate the stock in parallel (~5–10 s)
          </p>
        </div>
      ) : (
        <AgentDebatePanel report={report} />
      )}
    </div>
  );
}

function StockPageSkeleton({ ticker }: { ticker: string }) {
  return (
    <div className="space-y-5 p-4 lg:p-6 animate-pulse">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-headline text-2xl font-bold text-on-surface">{ticker}</h1>
          <p className="text-xs text-on-surface-variant mt-1">
            Computing 5-factor score — first load takes 10-30 s on cold start…
          </p>
        </div>
        <div className="h-10 w-28 rounded-lg bg-surface-container" />
      </div>
      <div className="grid md:grid-cols-3 gap-5">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-40 rounded-2xl bg-surface-container" />
        ))}
      </div>
      <div className="h-16 rounded-2xl bg-surface-container" />
      <div className="h-64 rounded-2xl bg-surface-container" />
      <div className="grid md:grid-cols-2 gap-5">
        <div className="h-48 rounded-2xl bg-surface-container" />
        <div className="h-48 rounded-2xl bg-surface-container" />
      </div>
      <div className="flex items-center justify-center gap-2 text-sm text-on-surface-variant py-4">
        <Loader2 size={14} className="animate-spin text-primary" />
        <span>Fetching ForeCast Score, meta, sentiment…</span>
      </div>
    </div>
  );
}

function SentimentCard({ s, ticker, market }: { s: SentimentResponse | null; ticker: string; market: Market }) {
  const color =
    !s ? "text-on-surface-variant"
    : s.label === "Bullish" ? "text-tertiary"
    : s.label === "Bearish" ? "text-error"
    : "text-secondary";
  return (
    <GhostBorderCard>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-xs text-on-surface-variant uppercase tracking-wide">News Sentiment</h3>
        <span className="text-xs text-on-surface-variant">VADER · {s?.n_headlines ?? 0} headlines</span>
      </div>
      {!s ? (
        <div className="text-sm text-on-surface-variant">Loading…</div>
      ) : s.n_headlines === 0 ? (
        <div className="text-sm text-on-surface-variant">No recent headlines for {ticker}.</div>
      ) : (
        <>
          <div className="flex items-baseline gap-3">
            <span className={`font-headline text-3xl font-bold ${color}`}>{s.label}</span>
            <span className="text-sm text-on-surface-variant tabular-nums">
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
                className="flex items-start justify-between gap-3 text-xs text-on-surface-variant hover:text-on-surface transition-colors"
              >
                <span className="leading-snug line-clamp-2">{h.title}</span>
                <span
                  className={`shrink-0 tabular-nums ${
                    h.score > 0 ? "text-tertiary" : h.score < 0 ? "text-error" : "text-on-surface-variant"
                  }`}
                >
                  {h.score >= 0 ? "+" : ""}{h.score.toFixed(2)}
                </span>
              </a>
            ))}
          </div>
        </>
      )}
    </GhostBorderCard>
  );
}

function BacktestCTA({ ticker, market }: { ticker: string; market: Market }) {
  return (
    <div className="bg-gradient-to-br from-primary/10 to-secondary/10 ghost-border rounded-2xl p-5 flex flex-col justify-between">
      <div>
        <h3 className="font-semibold text-xs text-on-surface-variant uppercase tracking-wide">Strategy Backtest</h3>
        <p className="text-sm text-on-surface-variant mt-2 leading-relaxed">
          Test a moving-average crossover on {ticker} — see Sharpe, max drawdown, and how it compares to buy-and-hold.
        </p>
      </div>
      <Link
        href={`/backtest?ticker=${ticker}&market=${market}`}
        className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary hover:bg-primary/80 text-on-surface text-sm font-medium w-fit transition-colors"
      >
        Run backtest <ArrowRight size={14} />
      </Link>
    </div>
  );
}
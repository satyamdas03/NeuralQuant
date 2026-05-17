"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { IndexData, NewsItem, SectorData, AIScore, Mover } from "@/lib/types";
import WelcomeModal from "@/components/onboarding/WelcomeModal";
import MarketIndexCard from "@/components/ui/MarketIndexCard";
import SectorHeatmapBlock from "@/components/ui/SectorHeatmapBlock";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import RegimeBadge from "@/components/ui/RegimeBadge";
import { ArrowUpRight, ArrowDownRight, TrendingUp, Newspaper } from "lucide-react";
import SocialBuzzCard from "@/components/ui/SocialBuzzCard";

// ─── Index Bar ────────────────────────────────────────────────────────────────

function IndexBar({ indices, loading }: { indices: IndexData[]; loading: boolean }) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-[72px] rounded-lg bg-surface-container animate-pulse" />
        ))}
      </div>
    );
  }
  if (!indices.length) {
    return (
      <GhostBorderCard className="text-center text-sm text-on-surface-variant">
        Market indices unavailable — start the API backend.
      </GhostBorderCard>
    );
  }
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {indices.map((d) => (
        <MarketIndexCard key={d.symbol} index={d} />
      ))}
    </div>
  );
}

// ─── News Panel ────────────────────────────────────────────────────────────────

function NewsPanel({ news, loading }: { news: NewsItem[]; loading: boolean }) {
  const [expanded, setExpanded] = useState<number | null>(0);

  return (
    <GhostBorderCard>
      <div className="flex items-center justify-between pb-3 border-b border-ghost-border">
        <div className="flex items-center gap-2">
          <Newspaper size={14} className="text-primary-fixed" />
          <h2 className="font-headline text-sm font-semibold text-on-surface">
            Market Summary
          </h2>
        </div>
        <span className="text-[10px] text-on-surface-variant">
          {news.length > 0 ? "Yahoo Finance" : loading ? "Fetching…" : "Unavailable"}
        </span>
      </div>

      {loading && !news.length ? (
        <div className="space-y-3 py-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-5 bg-surface-high rounded animate-pulse" style={{ width: `${85 - i * 8}%` }} />
          ))}
        </div>
      ) : !news.length ? (
        <p className="py-6 text-center text-sm text-on-surface-variant">
          News unavailable — backend may not be running.
        </p>
      ) : (
        <div className="divide-y divide-ghost-border/50">
          {news.map((item, i) => (
            <div key={i} className="py-2.5">
              <button
                onClick={() => setExpanded(expanded === i ? null : i)}
                className="w-full text-left"
              >
                <span className="text-sm text-on-surface leading-snug">{item.title}</span>
              </button>
              {expanded === i && (
                <div className="mt-1.5 flex items-center gap-3 text-xs text-on-surface-variant">
                  {item.publisher && <span className="text-primary">{item.publisher}</span>}
                  {item.url && (
                    <a href={item.url} target="_blank" rel="noopener noreferrer" className="hover:text-secondary underline">
                      Read →
                    </a>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </GhostBorderCard>
  );
}

// ─── Market Movers ──────────────────────────────────────────────────────────────

function MoversPanel({ gainers, losers, active, loading }: {
  gainers: Mover[]; losers: Mover[]; active: Mover[]; loading: boolean;
}) {
  const [tab, setTab] = useState<"gainers" | "losers" | "active">("gainers");
  const rows = tab === "gainers" ? gainers : tab === "losers" ? losers : active;

  return (
    <GhostBorderCard>
      <div className="flex border-b border-ghost-border">
        {(["gainers", "losers", "active"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-2 text-xs font-semibold uppercase tracking-wide transition-colors ${
              tab === t
                ? "text-secondary border-b-2 border-secondary"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {loading && !rows.length ? (
        <div className="space-y-3 p-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="flex justify-between">
              <div className="h-4 w-16 bg-surface-high rounded animate-pulse" />
              <div className="h-4 w-12 bg-surface-high rounded animate-pulse" />
            </div>
          ))}
        </div>
      ) : !rows.length ? (
        <p className="py-6 text-center text-xs text-on-surface-variant">Data unavailable</p>
      ) : (
        <div className="divide-y divide-ghost-border/50">
          {rows.map((m) => (
            <Link
              key={m.ticker}
              href={`/stocks/${m.ticker}`}
              className="flex items-center justify-between px-4 py-2.5 hover:bg-surface-high transition-colors"
            >
              <div>
                <div className="text-sm font-semibold text-on-surface">{m.ticker}</div>
                <div className="tabular-nums text-xs text-on-surface-variant">
                  ${m.price.toLocaleString()}
                </div>
              </div>
              <span
                className={`flex items-center gap-1 tabular-nums text-sm font-bold ${
                  m.change_pct >= 0 ? "text-tertiary" : "text-error"
                }`}
              >
                {m.change_pct >= 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                {m.change_pct >= 0 ? "+" : ""}{m.change_pct.toFixed(2)}%
              </span>
            </Link>
          ))}
        </div>
      )}
    </GhostBorderCard>
  );
}

// ─── Top AI Picks ───────────────────────────────────────────────────────────────

function TopAIPicks({ stocks, regime, loading }: { stocks: AIScore[]; regime: string; loading: boolean }) {
  return (
    <GhostBorderCard>
      <div className="flex items-center justify-between pb-3 border-b border-ghost-border">
        <div className="flex items-center gap-2">
          <TrendingUp size={14} className="text-tertiary-fixed-dim" />
          <h2 className="font-headline text-sm font-semibold text-on-surface">Top ForeCast Picks</h2>
        </div>
        {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
        {regime && <RegimeBadge label={regime as any} />}
      </div>

      {loading && !stocks.length ? (
        <div className="space-y-3 p-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="flex gap-3">
              <div className="h-4 w-4 bg-surface-high rounded animate-pulse" />
              <div className="flex-1 h-4 bg-surface-high rounded animate-pulse" />
              <div className="h-4 w-10 bg-surface-high rounded animate-pulse" />
            </div>
          ))}
        </div>
      ) : !stocks.length ? (
        <div className="p-4 text-center text-sm text-on-surface-variant">
          Scores are computing — refresh in a minute.
        </div>
      ) : (
        <>
          <div className="divide-y divide-ghost-border/50">
            {stocks.slice(0, 8).map((s, i) => (
              <Link
                key={s.ticker}
                href={`/stocks/${s.ticker}?market=${s.market}`}
                className="flex items-center gap-3 px-4 py-3 hover:bg-surface-high transition-colors"
              >
                <span className="text-xs text-on-surface-variant w-4">{i + 1}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-on-surface">{s.ticker}</div>
                  <div className="text-xs text-on-surface-variant">{s.market}</div>
                </div>
                <div className="text-right">
                  <div className="tabular-nums text-base font-bold text-primary">
                    {s.score_1_10}
                    <span className="text-xs text-on-surface-variant">/10</span>
                  </div>
                  <div className="text-[10px] text-on-surface-variant capitalize">{s.confidence}</div>
                </div>
              </Link>
            ))}
          </div>
          <div className="px-4 py-3 border-t border-ghost-border">
            <Link href="/screener" className="text-xs text-primary-fixed hover:text-primary transition-colors">
              View full screener →
            </Link>
          </div>
        </>
      )}
    </GhostBorderCard>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [showOnboarding, setShowOnboarding] = useState(false);

  useEffect(() => {
    // Always show welcome modal — user can skip if they want
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setShowOnboarding(true);
  }, []);

  const [indices, setIndices] = useState<IndexData[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [sectors, setSectors] = useState<SectorData[]>([]);
  const [topStocks, setTopStocks] = useState<AIScore[]>([]);
  const [regime, setRegime] = useState("");
  const [gainers, setGainers] = useState<Mover[]>([]);
  const [losers, setLosers] = useState<Mover[]>([]);
  const [active, setActive] = useState<Mover[]>([]);
  const [indicesLoading, setIndicesLoading] = useState(true);
  const [newsLoading, setNewsLoading] = useState(true);
  const [sectorsLoading, setSectorsLoading] = useState(true);
  const [stocksLoading, setStocksLoading] = useState(true);
  const [moversLoading, setMoversLoading] = useState(true);

  useEffect(() => {
    api.getMarketOverview()
      .then((d) => setIndices(d.indices))
      .catch((e) => console.error("market/overview failed:", e))
      .finally(() => setIndicesLoading(false));

    api.getMarketNews(8)
      .then((d) => setNews(d.news))
      .catch((e) => console.error("market/news failed:", e))
      .finally(() => setNewsLoading(false));

    api.getMarketSectors()
      .then((d) => setSectors(d.sectors))
      .catch((e) => console.error("market/sectors failed:", e))
      .finally(() => setSectorsLoading(false));

    api.getScreenerPreview("US", 8)
      .then((d) => { setTopStocks(d.results); setRegime(d.regime_label); })
      .catch((e) => console.error("screener/preview failed:", e))
      .finally(() => setStocksLoading(false));

    api.getMarketMovers()
      .then((d) => { setGainers(d.gainers); setLosers(d.losers); setActive(d.active); })
      .catch((e) => console.error("market/movers failed:", e))
      .finally(() => setMoversLoading(false));
  }, []);

  return (
    <div className="space-y-5 p-4 lg:p-6">
      {showOnboarding && <WelcomeModal onClose={() => setShowOnboarding(false)} />}
      {/* Market Indices */}
      <div id="dashboard-market-indices">
        <IndexBar indices={indices} loading={indicesLoading} />
      </div>

      {/* Bento Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-5">
        {/* Left column */}
        <div className="space-y-5">
          <div id="dashboard-news-panel">
            <NewsPanel news={news} loading={newsLoading} />
          </div>
          <GhostBorderCard id="dashboard-equity-sectors">
            <div className="flex items-center gap-2 pb-3 border-b border-ghost-border">
              <TrendingUp size={14} className="text-primary-fixed" />
              <h2 className="font-headline text-sm font-semibold text-on-surface">Equity Sectors</h2>
            </div>
            {sectorsLoading && !sectors.length ? (
              <div className="grid grid-cols-3 gap-2 p-4 sm:grid-cols-4">
                {[...Array(11)].map((_, i) => (
                  <div key={i} className="h-16 rounded-lg bg-surface-high animate-pulse" />
                ))}
              </div>
            ) : !sectors.length ? (
              <p className="py-6 text-center text-sm text-on-surface-variant">Sector data unavailable</p>
            ) : (
              <div className="p-4">
                <SectorHeatmapBlock sectors={sectors} />
              </div>
            )}
          </GhostBorderCard>
          <div id="dashboard-forecast-picks">
            <TopAIPicks stocks={topStocks} regime={regime} loading={stocksLoading} />
          </div>
        </div>

        {/* Right sidebar */}
        <div className="space-y-5">
          <div id="dashboard-market-movers">
            <MoversPanel gainers={gainers} losers={losers} active={active} loading={moversLoading} />
          </div>
          <div id="dashboard-social-buzz">
            <SocialBuzzCard />
          </div>
        </div>
      </div>
    </div>
  );
}
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { IndexData, NewsItem, SectorData, AIScore, Mover } from "@/lib/types";

// ─── Market Indices Bar ────────────────────────────────────────────────────────

function IndexCard({ d }: { d: IndexData }) {
  const up = d.change_pct >= 0;
  return (
    <div className="flex-1 min-w-[150px] bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-700 transition-colors">
      <div className="text-xs text-gray-500 font-medium uppercase tracking-wide">{d.name}</div>
      <div className="text-xl font-bold mt-1 tabular-nums">
        {d.symbol === "^VIX"
          ? d.price.toFixed(2)
          : d.price.toLocaleString("en-US", { maximumFractionDigits: 2 })}
      </div>
      <div className={`text-sm font-medium mt-0.5 ${up ? "text-emerald-400" : "text-red-400"}`}>
        {up ? "▲" : "▼"} {Math.abs(d.change_pct).toFixed(2)}%{" "}
        <span className="text-gray-500 font-normal">
          ({up ? "+" : ""}
          {d.change_abs.toFixed(2)})
        </span>
      </div>
    </div>
  );
}

function IndexSkeleton() {
  return (
    <div className="flex-1 min-w-[150px] bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="text-xs text-gray-600">Loading…</div>
      <div className="h-7 w-24 bg-gray-800 rounded animate-pulse mt-2" />
      <div className="h-4 w-16 bg-gray-800 rounded animate-pulse mt-2" />
    </div>
  );
}

// ─── News Section ─────────────────────────────────────────────────────────────

function NewsSection({ news, loading }: { news: NewsItem[]; loading: boolean }) {
  const [expanded, setExpanded] = useState<number | null>(0);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-800">
        <h2 className="font-semibold text-sm text-gray-300 uppercase tracking-wide">
          Market Summary
        </h2>
        <span className="text-xs text-gray-500">
          {news.length > 0 ? "Live via Yahoo Finance" : loading ? "Fetching…" : "Unavailable"}
        </span>
      </div>

      {loading && news.length === 0 ? (
        <div className="p-5 space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-5 bg-gray-800 rounded animate-pulse" style={{ width: `${85 - i * 8}%` }} />
          ))}
        </div>
      ) : news.length === 0 ? (
        <div className="px-5 py-8 text-center text-sm text-gray-600">
          <p>Live news unavailable — backend may not be running.</p>
          <p className="mt-1 text-xs">
            Start the API:{" "}
            <code className="bg-gray-800 px-2 py-0.5 rounded text-violet-400">
              uvicorn nq_api.main:app --reload
            </code>
          </p>
        </div>
      ) : (
        <div className="divide-y divide-gray-800">
          {news.map((item, i) => (
            <div key={i} className="px-5 py-3">
              <button className="w-full text-left" onClick={() => setExpanded(expanded === i ? null : i)}>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-sm font-medium text-gray-100 hover:text-white leading-snug">
                    {item.title}
                  </span>
                  <span className="text-gray-600 text-xs mt-0.5 shrink-0">{expanded === i ? "▲" : "▼"}</span>
                </div>
              </button>
              {expanded === i && (
                <div className="mt-2 flex items-center gap-3 text-xs text-gray-500">
                  {item.publisher && <span className="text-violet-400">{item.publisher}</span>}
                  {item.url && (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-gray-300 underline"
                    >
                      Read full article →
                    </a>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Sector Heatmap ───────────────────────────────────────────────────────────

function SectorHeatmap({ sectors, loading }: { sectors: SectorData[]; loading: boolean }) {
  const max = Math.max(...sectors.map((s) => Math.abs(s.change_pct)), 1);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-800">
        <h2 className="font-semibold text-sm text-gray-300 uppercase tracking-wide">Equity Sectors</h2>
      </div>
      {loading && sectors.length === 0 ? (
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 p-4">
          {[...Array(11)].map((_, i) => (
            <div key={i} className="rounded-lg p-3 bg-gray-800 animate-pulse h-16" />
          ))}
        </div>
      ) : sectors.length === 0 ? (
        <div className="px-5 py-6 text-center text-sm text-gray-600">
          Sector data unavailable. Check backend is running.
        </div>
      ) : (
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 p-4">
          {sectors.map((s) => {
            const pct = s.change_pct;
            const intensity = Math.min(Math.abs(pct) / max, 1);
            const bg =
              pct > 0
                ? `rgba(16,185,129,${0.12 + intensity * 0.35})`
                : `rgba(239,68,68,${0.12 + intensity * 0.35})`;
            return (
              <div key={s.symbol} className="rounded-lg p-3 text-center" style={{ background: bg }}>
                <div className="text-xs font-medium text-gray-200 truncate">{s.name}</div>
                <div
                  className={`text-sm font-bold mt-0.5 ${pct >= 0 ? "text-emerald-400" : "text-red-400"}`}
                >
                  {pct >= 0 ? "+" : ""}
                  {pct.toFixed(2)}%
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Inline NL Query Box ──────────────────────────────────────────────────────

function HomeQueryBox() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    const q = question.trim();
    if (!q || loading) return;
    setLoading(true);
    setAnswer("");
    try {
      const res = await api.runQuery({ question: q });
      setAnswer(res.answer);
    } catch {
      setAnswer("Failed — check backend is running and ANTHROPIC_API_KEY is set in apps/api/.env");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-800">
        <h2 className="font-semibold text-sm text-gray-300 uppercase tracking-wide">
          Ask anything about markets
        </h2>
      </div>
      <div className="p-4 space-y-3">
        <div className="flex gap-2">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder="e.g. What is the effect of Iran-US tensions on oil stocks?"
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-violet-500"
          />
          <button
            onClick={submit}
            disabled={loading || !question.trim()}
            className="px-4 py-2.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 rounded-lg text-sm font-medium transition-colors"
          >
            {loading ? "…" : "→"}
          </button>
        </div>
        {answer && (
          <div className="text-sm text-gray-300 leading-relaxed bg-gray-800/50 rounded-lg p-4 whitespace-pre-wrap">
            {answer}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Market Movers ────────────────────────────────────────────────────────────

function MarketMoversPanel({ gainers, losers, active, loading }: {
  gainers: Mover[]; losers: Mover[]; active: Mover[]; loading: boolean;
}) {
  const [tab, setTab] = useState<"gainers" | "losers" | "active">("gainers");
  const rows = tab === "gainers" ? gainers : tab === "losers" ? losers : active;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="flex border-b border-gray-800">
        {(["gainers", "losers", "active"] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-2.5 text-xs font-semibold uppercase tracking-wider transition-colors ${
              tab === t
                ? "text-white border-b-2 border-violet-500 bg-gray-800/40"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {loading && rows.length === 0 ? (
        <div className="p-4 space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex justify-between">
              <div className="h-4 w-16 bg-gray-800 rounded animate-pulse" />
              <div className="h-4 w-16 bg-gray-800 rounded animate-pulse" />
            </div>
          ))}
        </div>
      ) : rows.length === 0 ? (
        <div className="px-4 py-6 text-center text-xs text-gray-600">Data unavailable</div>
      ) : (
        <div className="divide-y divide-gray-800">
          {rows.map(m => (
            <Link
              key={m.ticker}
              href={`/stocks/${m.ticker}`}
              className="flex items-center justify-between px-4 py-2.5 hover:bg-gray-800/50 transition-colors"
            >
              <div>
                <div className="text-sm font-semibold text-gray-100">{m.ticker}</div>
                <div className="text-xs text-gray-500 tabular-nums">${m.price.toLocaleString()}</div>
              </div>
              <span className={`text-sm font-bold tabular-nums ${m.change_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {m.change_pct >= 0 ? "+" : ""}{m.change_pct.toFixed(2)}%
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Top AI Picks Sidebar ─────────────────────────────────────────────────────

function TopAIPicks({
  stocks,
  regime,
  loading,
}: {
  stocks: AIScore[];
  regime: string;
  loading: boolean;
}) {
  const scoreColor = (s: number) =>
    s >= 7 ? "text-emerald-400" : s >= 5 ? "text-yellow-400" : "text-red-400";

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
        <h2 className="font-semibold text-sm text-gray-300 uppercase tracking-wide">Top AI Picks</h2>
        {regime && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            {regime}
          </span>
        )}
      </div>

      {loading && stocks.length === 0 ? (
        <div className="p-4 space-y-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="flex gap-3">
              <div className="h-4 w-4 bg-gray-800 rounded animate-pulse" />
              <div className="flex-1 h-4 bg-gray-800 rounded animate-pulse" />
              <div className="h-4 w-10 bg-gray-800 rounded animate-pulse" />
            </div>
          ))}
        </div>
      ) : (
        <>
          <div className="divide-y divide-gray-800">
            {stocks.slice(0, 8).map((s, i) => (
              <Link
                key={s.ticker}
                href={`/stocks/${s.ticker}?market=${s.market}`}
                className="flex items-center gap-3 px-4 py-3 hover:bg-gray-800/60 transition-colors"
              >
                <span className="text-xs text-gray-600 w-4">{i + 1}</span>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-sm text-gray-100">{s.ticker}</div>
                  <div className="text-xs text-gray-500">{s.market}</div>
                </div>
                <div className="text-right">
                  <div className={`text-base font-bold tabular-nums ${scoreColor(s.score_1_10)}`}>
                    {s.score_1_10}
                    <span className="text-xs text-gray-500">/10</span>
                  </div>
                  <div className="text-xs text-gray-500">{s.confidence}</div>
                </div>
              </Link>
            ))}
          </div>
          <div className="px-4 py-3 border-t border-gray-800">
            <Link href="/screener" className="text-xs text-violet-400 hover:text-violet-300 transition-colors">
              View full screener →
            </Link>
          </div>
        </>
      )}
    </div>
  );
}

// ─── Sector List Sidebar ──────────────────────────────────────────────────────

function SectorList({ sectors, loading }: { sectors: SectorData[]; loading: boolean }) {
  const sorted = [...sectors].sort((a, b) => b.change_pct - a.change_pct);
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-800">
        <h2 className="font-semibold text-sm text-gray-300 uppercase tracking-wide">Sector Performance</h2>
      </div>
      {loading && sectors.length === 0 ? (
        <div className="p-4 space-y-2">
          {[...Array(7)].map((_, i) => (
            <div key={i} className="flex justify-between">
              <div className="h-4 w-32 bg-gray-800 rounded animate-pulse" />
              <div className="h-4 w-12 bg-gray-800 rounded animate-pulse" />
            </div>
          ))}
        </div>
      ) : sectors.length === 0 ? (
        <div className="px-4 py-4 text-center text-xs text-gray-600">Sector data unavailable</div>
      ) : (
        <div className="divide-y divide-gray-800">
          {sorted.map((s) => (
            <div key={s.symbol} className="flex items-center justify-between px-4 py-2.5">
              <span className="text-sm text-gray-300 truncate">{s.name}</span>
              <span
                className={`text-sm font-medium tabular-nums ${
                  s.change_pct >= 0 ? "text-emerald-400" : "text-red-400"
                }`}
              >
                {s.change_pct >= 0 ? "+" : ""}
                {s.change_pct.toFixed(2)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function Home() {
  const [indices, setIndices] = useState<IndexData[]>([]);
  const [futures, setFutures] = useState<IndexData[]>([]);
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
      .then((d) => { setIndices(d.indices); setFutures(d.futures ?? []); })
      .catch(() => {})
      .finally(() => setIndicesLoading(false));

    api.getMarketNews(8)
      .then((d) => setNews(d.news))
      .catch(() => {})
      .finally(() => setNewsLoading(false));

    api.getMarketSectors()
      .then((d) => setSectors(d.sectors))
      .catch(() => {})
      .finally(() => setSectorsLoading(false));

    api.runScreener({ market: "US", max_results: 8 })
      .then((d) => { setTopStocks(d.results); setRegime(d.regime_label); })
      .catch(() => {})
      .finally(() => setStocksLoading(false));

    api.getMarketMovers()
      .then((d) => { setGainers(d.gainers); setLosers(d.losers); setActive(d.active); })
      .catch(() => {})
      .finally(() => setMoversLoading(false));
  }, []);

  return (
    <div className="space-y-5">
      {/* Market Indices Bar */}
      <div className="space-y-2">
        <div className="flex flex-wrap gap-3">
          {indicesLoading
            ? [1, 2, 3, 4].map((i) => <IndexSkeleton key={i} />)
            : indices.length > 0
            ? indices.map((d) => <IndexCard key={d.symbol} d={d} />)
            : (
              <div className="w-full bg-gray-900 border border-gray-800 rounded-xl px-5 py-4 text-sm text-gray-500">
                Live market indices unavailable.{" "}
                <span className="text-gray-600">Restart the FastAPI backend to load real-time data.</span>
              </div>
            )}
        </div>
        {futures.length > 0 && (
          <div className="flex flex-wrap gap-3 items-center">
            <span className="text-xs text-gray-600 uppercase tracking-widest font-semibold px-1 min-w-[60px]">Futures</span>
            {futures.map((d) => <IndexCard key={d.symbol} d={d} />)}
          </div>
        )}
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-5">
        {/* Left column */}
        <div className="space-y-5">
          <NewsSection news={news} loading={newsLoading} />
          <HomeQueryBox />
          <SectorHeatmap sectors={sectors} loading={sectorsLoading} />
        </div>

        {/* Right sidebar */}
        <div className="space-y-5">
          <MarketMoversPanel
            gainers={gainers} losers={losers} active={active} loading={moversLoading}
          />
          <TopAIPicks stocks={topStocks} regime={regime} loading={stocksLoading} />
          <SectorList sectors={sectors} loading={sectorsLoading} />
        </div>
      </div>
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
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

// ─── Inline NL Query Box (full chat with history + cold-start banner) ─────────

interface HomeChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  followUps?: string[];
  loading?: boolean;
}

const HOME_EXAMPLES = [
  "What is the effect of Iran-US tensions on oil stocks?",
  "Should I invest in Trent right now?",
  "I want to invest ₹10L in Indian stocks — which ones?",
  "Give me a 1-month outlook for TCS",
];

function HomeQueryBox() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<HomeChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [slowLoad, setSlowLoad] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const slowTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const ask = async (question: string) => {
    const q = question.trim();
    if (!q || loading) return;
    setInput("");
    setSlowLoad(false);

    const userMsg: HomeChatMessage = { id: Date.now().toString(), role: "user", content: q };
    const placeholderId = (Date.now() + 1).toString();
    const placeholder: HomeChatMessage = { id: placeholderId, role: "assistant", content: "", loading: true };

    setMessages(prev => [...prev, userMsg, placeholder]);
    setLoading(true);

    // After 8s still loading → show cold-start warning
    slowTimer.current = setTimeout(() => setSlowLoad(true), 8000);

    // Build conversation history from prior completed turns
    const history = messages
      .filter(m => !m.loading)
      .map(m => ({ role: m.role as "user" | "assistant", content: m.content }));

    try {
      const res = await api.runQuery({ question: q, history });
      setMessages(prev =>
        prev.map(m =>
          m.id === placeholderId
            ? { ...m, content: res.answer, sources: res.data_sources, followUps: res.follow_up_questions, loading: false }
            : m
        )
      );
    } catch {
      setMessages(prev =>
        prev.map(m =>
          m.id === placeholderId
            ? { ...m, content: "Failed — backend may be starting up. Please try again in 30 seconds.", loading: false }
            : m
        )
      );
    } finally {
      setLoading(false);
      setSlowLoad(false);
      if (slowTimer.current) clearTimeout(slowTimer.current);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const clear = () => { setMessages([]); setInput(""); };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-800 flex items-center justify-between">
        <h2 className="font-semibold text-sm text-gray-300 uppercase tracking-wide">
          Ask anything about markets
        </h2>
        {messages.length > 0 && (
          <button onClick={clear} className="text-xs text-gray-600 hover:text-gray-400 transition-colors">
            Clear
          </button>
        )}
      </div>

      {/* Cold-start banner */}
      {slowLoad && (
        <div className="mx-4 mt-3 px-4 py-2.5 bg-amber-500/10 border border-amber-500/30 rounded-lg flex items-center gap-2">
          <span className="text-amber-400 text-xs">⚡</span>
          <span className="text-amber-300 text-xs">
            Backend is warming up after inactivity — this may take 30–60 seconds. Please wait…
          </span>
        </div>
      )}

      <div className="p-4 space-y-3">
        {/* Chat history */}
        {messages.length > 0 ? (
          <div className="space-y-3 max-h-[50vh] overflow-y-auto pr-1 scroll-smooth">
            {messages.map(msg => (
              <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                {msg.role === "user" ? (
                  <div className="max-w-[80%] bg-violet-600/20 border border-violet-500/20 rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm text-gray-100">
                    {msg.content}
                  </div>
                ) : (
                  <div className="max-w-[95%] space-y-2">
                    <div className="flex items-start gap-2">
                      <div className="w-5 h-5 rounded-full bg-gradient-to-br from-violet-500 to-cyan-500 flex-shrink-0 flex items-center justify-center mt-0.5">
                        <span className="text-[9px] font-bold text-white">N</span>
                      </div>
                      <div className="bg-gray-800/60 border border-gray-700/50 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-gray-100 leading-relaxed">
                        {msg.loading ? (
                          <div className="flex gap-1.5 items-center py-1">
                            {[0, 1, 2].map(i => (
                              <span
                                key={i}
                                className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce"
                                style={{ animationDelay: `${i * 0.15}s` }}
                              />
                            ))}
                          </div>
                        ) : (
                          <p className="whitespace-pre-wrap">{msg.content}</p>
                        )}
                      </div>
                    </div>
                    {/* Sources */}
                    {!msg.loading && msg.sources && msg.sources.length > 0 && (
                      <div className="ml-7 flex gap-1.5 flex-wrap">
                        {msg.sources.map(s => (
                          <span key={s} className="text-[10px] px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20">
                            {s}
                          </span>
                        ))}
                      </div>
                    )}
                    {/* Follow-up chips */}
                    {!msg.loading && msg.followUps && msg.followUps.length > 0 && (
                      <div className="ml-7 flex flex-wrap gap-1.5">
                        {msg.followUps.map(q => (
                          <button
                            key={q}
                            onClick={() => ask(q)}
                            className="text-xs px-3 py-1 bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white rounded-full transition-colors border border-gray-700"
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        ) : (
          /* Empty state: example chips */
          <div className="flex flex-wrap gap-2 pb-1">
            {HOME_EXAMPLES.map(q => (
              <button
                key={q}
                onClick={() => ask(q)}
                className="text-xs px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white rounded-full transition-colors border border-gray-700"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {/* Input bar */}
        <div className="flex gap-2">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && ask(input)}
            placeholder="Ask about any stock or market…"
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-violet-500 transition-colors"
            disabled={loading}
          />
          <button
            onClick={() => ask(input)}
            disabled={loading || !input.trim()}
            className="px-4 py-2.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 rounded-lg text-sm font-medium transition-colors"
          >
            {loading ? (
              <span className="w-3.5 h-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin block" />
            ) : "→"}
          </button>
        </div>
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

    api.getScreenerPreview("US", 8)
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

"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { IndexData, NewsItem, SectorData, AIScore, Mover } from "@/lib/types";
import WelcomeModal from "@/components/onboarding/WelcomeModal";
import MarketIndexCard from "@/components/ui/MarketIndexCard";
import SectorHeatmapBlock from "@/components/ui/SectorHeatmapBlock";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import RegimeBadge from "@/components/ui/RegimeBadge";
import SuggestionChips from "@/components/ui/SuggestionChips";
import ChatInputArea from "@/components/ui/ChatInputArea";
import AIResponseCard from "@/components/ui/AIResponseCard";
import GlassPanel from "@/components/ui/GlassPanel";
import { ArrowUpRight, ArrowDownRight, TrendingUp, Newspaper, Zap, Swords } from "lucide-react";
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
          <Newspaper size={14} className="text-secondary" />
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

// ─── Inline Ask AI ─────────────────────────────────────────────────────────────

interface ChatMsg {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  followUps?: string[];
  loading?: boolean;
  structured?: import("@/lib/types").StructuredQueryResponse | null;
  phaseLabel?: string;
}

const EXAMPLES = [
  "What is the effect of Iran-US tensions on oil stocks?",
  "Should I invest in Trent right now?",
  "1-month outlook for TCS",
  "Best Indian stocks for ₹10L investment",
];

function HomeAskAI() {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [loading, setLoading] = useState(false);
  const [slowLoad, setSlowLoad] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const slowTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const ask = async (question: string) => {
    const q = question.trim();
    if (!q || loading) return;
    setSlowLoad(false);

    // Check auth first to avoid redirect on 401
    try {
      const { createClient } = await import("@/lib/supabase/client");
      const supabase = createClient();
      const { data } = await supabase.auth.getSession();
      if (!data.session?.access_token) {
        const userMsg: ChatMsg = { id: Date.now().toString(), role: "user", content: q };
        const authMsg: ChatMsg = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: "Sign in required to ask questions.",
          loading: false,
        };
        setMessages((prev) => [...prev, userMsg, authMsg]);
        return;
      }
    } catch { /* proceed without check */ }

    const userMsg: ChatMsg = { id: Date.now().toString(), role: "user", content: q };
    const phId = (Date.now() + 1).toString();
    const ph: ChatMsg = { id: phId, role: "assistant", content: "", loading: true, phaseLabel: "Thinking..." };

    setMessages((prev) => [...prev, userMsg, ph]);
    setLoading(true);
    slowTimer.current = setTimeout(() => setSlowLoad(true), 8000);

    const history = messages
      .filter((m) => !m.loading)
      .map((m) => ({ role: m.role, content: m.content }));

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 300_000);

    try {
      const res = await api.runQueryStream(
        { question: q, history },
        controller.signal,
        (phase, label) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === phId ? { ...m, phaseLabel: label } : m
            )
          );
        },
      );
      setMessages((prev) =>
        prev.map((m) =>
          m.id === phId
            ? { ...m, content: res.summary || "", sources: res.data_sources, followUps: res.follow_up_questions, loading: false, structured: res, phaseLabel: undefined }
            : m
        )
      );
    } catch (e) {
      const errMsg = e instanceof Error && e.message.includes("auth required")
        ? "Sign in required to ask questions."
        : e instanceof DOMException && e.name === "AbortError"
        ? "Query timed out after 5 minutes. Try a shorter question or retry."
        : "Failed — backend may be starting. Retry in 30s.";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === phId
            ? { ...m, content: errMsg, loading: false, phaseLabel: undefined }
            : m
        )
      );
    } finally {
      clearTimeout(timeout);
      setLoading(false);
      setSlowLoad(false);
      if (slowTimer.current) clearTimeout(slowTimer.current);
    }
  };

  return (
    <GlassPanel strong>
      <div className="flex items-center justify-between pb-3 border-b border-ghost-border">
        <div className="flex items-center gap-2">
          <Zap size={14} className="text-primary" />
          <h2 className="font-headline text-sm font-semibold text-on-surface">
            Ask anything about markets
          </h2>
          <Link href="/screener" className="inline-flex items-center gap-2 text-sm text-secondary hover:underline">
            <Swords size={16} /> Debate a stock
          </Link>
        </div>
        {messages.length > 0 && (
          <button
            onClick={() => setMessages([])}
            className="text-xs text-on-surface-variant hover:text-on-surface transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {slowLoad && (
        <div className="mt-3 rounded-lg bg-primary/10 px-3 py-2 text-xs text-primary border border-primary/20">
          Backend warming up — may take 30–60s. Please wait…
        </div>
      )}

      <div className="mt-3 space-y-3">
        {messages.length > 0 ? (
          <div className="max-h-[50vh] space-y-3 overflow-y-auto pr-1 scroll-smooth">
            {messages.map((msg) =>
              msg.role === "user" ? (
                <div key={msg.id} className="flex justify-end">
                  <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-primary/15 border border-primary/20 px-4 py-2.5 text-sm text-on-surface">
                    {msg.content}
                  </div>
                </div>
              ) : msg.content === "Sign in required to ask questions." ? (
                <div key={msg.id} className="flex justify-start">
                  <div className="max-w-[80%] rounded-2xl rounded-tl-sm bg-surface-container border border-ghost-border px-4 py-2.5 text-sm text-on-surface-variant">
                    Sign in required to ask questions.{" "}
                    <Link href="/login" className="text-primary hover:underline">Sign in →</Link>
                  </div>
                </div>
              ) : (
                <AIResponseCard
                  key={msg.id}
                  answer={msg.loading ? "…" : msg.content}
                  sources={msg.loading ? [] : msg.sources}
                  structured={msg.structured}
                />
              )
            )}
            {messages.some((m) => m.loading) && (() => {
              const loadingMsg = messages.find((m) => m.loading);
              return (
                <div className="flex items-center gap-2 py-1 text-sm text-on-surface-variant">
                  <span className="animate-pulse text-primary">●</span>
                  <span>{loadingMsg?.phaseLabel || "Thinking..."}</span>
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className="h-1.5 w-1.5 rounded-full bg-primary animate-bounce"
                      style={{ animationDelay: `${i * 0.15}s` }}
                    />
                  ))}
                </div>
              );
            })()}
            {messages.length > 0 && !loading && messages[messages.length - 1].followUps && (
              <SuggestionChips
                suggestions={messages[messages.length - 1].followUps!}
                onSelect={ask}
              />
            )}
            <div ref={bottomRef} />
          </div>
        ) : (
          <SuggestionChips suggestions={EXAMPLES} onSelect={ask} />
        )}

        <ChatInputArea onSubmit={ask} disabled={loading} />
      </div>
    </GlassPanel>
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
          <TrendingUp size={14} className="text-tertiary" />
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
            <Link href="/screener" className="text-xs text-secondary hover:text-primary transition-colors">
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
    const seen = localStorage.getItem("nq_onboarding_seen");
    if (!seen) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setShowOnboarding(true);
      localStorage.setItem("nq_onboarding_seen", "1");
    }
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
      <IndexBar indices={indices} loading={indicesLoading} />

      {/* Bento Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-5">
        {/* Left column */}
        <div className="space-y-5">
          <NewsPanel news={news} loading={newsLoading} />
          <HomeAskAI />
          <GhostBorderCard>
            <div className="flex items-center gap-2 pb-3 border-b border-ghost-border">
              <TrendingUp size={14} className="text-secondary" />
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
        </div>

        {/* Right sidebar */}
        <div className="space-y-5">
          <MoversPanel gainers={gainers} losers={losers} active={active} loading={moversLoading} />
          <TopAIPicks stocks={topStocks} regime={regime} loading={stocksLoading} />
          <SocialBuzzCard />
        </div>
      </div>
    </div>
  );
}
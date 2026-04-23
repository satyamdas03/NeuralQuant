"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { NewsDeskItem, NewsDeskResponse } from "@/lib/types";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import GlassPanel from "@/components/ui/GlassPanel";
import {
  Newspaper,
  TrendingUp,
  TrendingDown,
  Minus,
  ArrowUpRight,
  Clock,
  ExternalLink,
  Radio,
} from "lucide-react";

// ─── Constants ────────────────────────────────────────────────────────────────

const CATEGORIES: { key: NewsDeskItem["category"] | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "us_markets", label: "US Markets" },
  { key: "india", label: "India" },
  { key: "earnings", label: "Earnings" },
  { key: "macro", label: "Macro" },
  { key: "insider", label: "Insider" },
];

const MOCK_NEWS: NewsDeskResponse = {
  sentiment: "bullish",
  headlines: [
    {
      title: "Fed signals potential rate cuts in Q3 as inflation cools",
      publisher: "Reuters",
      url: "https://finance.yahoo.com/news/fed-rate-cuts",
      time: "2h ago",
      category: "macro",
      tickers: ["SPY", "QQQ", "TLT"],
      sentiment: "bullish",
    },
    {
      title: "NVIDIA announces next-gen Blackwell chips, orders surge 40%",
      publisher: "Bloomberg",
      url: "https://finance.yahoo.com/news/nvidia-blackwell",
      time: "3h ago",
      category: "us_markets",
      tickers: ["NVDA", "AMD", "SMCI"],
      sentiment: "bullish",
    },
    {
      title: "TCS beats Q4 estimates with 8.2% revenue growth in constant currency",
      publisher: "Economic Times",
      url: "https://finance.yahoo.com/news/tcs-q4-results",
      time: "4h ago",
      category: "india",
      tickers: ["TCS.NS", "INFY.NS", "WIPRO.NS"],
      sentiment: "bullish",
    },
    {
      title: "Apple faces antitrust suit from DOJ over App Store monopoly claims",
      publisher: "Wall Street Journal",
      url: "https://finance.yahoo.com/news/apple-doj-antitrust",
      time: "5h ago",
      category: "us_markets",
      tickers: ["AAPL", "GOOGL", "META"],
      sentiment: "bearish",
    },
    {
      title: "Reliance Industries greenlights $10B renewable energy expansion",
      publisher: "Moneycontrol",
      url: "https://finance.yahoo.com/news/reliance-renewable-energy",
      time: "6h ago",
      category: "india",
      tickers: ["RELIANCE.NS", "TATAPOWER.NS"],
      sentiment: "bullish",
    },
    {
      title: "Microsoft Azure revenue jumps 31%, cloud wars intensify",
      publisher: "CNBC",
      url: "https://finance.yahoo.com/news/microsoft-azure-revenue",
      time: "7h ago",
      category: "earnings",
      tickers: ["MSFT", "AMZN", "GOOGL"],
      sentiment: "bullish",
    },
    {
      title: "CEO of Palantir sells $45M in shares amid volatility spike",
      publisher: "SEC Filings",
      url: "https://finance.yahoo.com/news/palantir-ceo-sells",
      time: "8h ago",
      category: "insider",
      tickers: ["PLTR"],
      sentiment: "bearish",
    },
    {
      title: "India GDP growth hits 7.8% in Q4, beating consensus 7.2%",
      publisher: "Business Standard",
      url: "https://finance.yahoo.com/news/india-gdp-q4",
      time: "9h ago",
      category: "macro",
      tickers: ["INDA", "EPI", "MINDX"],
      sentiment: "bullish",
    },
    {
      title: "Tesla deliveries miss estimates by 12% in first quarter",
      publisher: "Financial Times",
      url: "https://finance.yahoo.com/news/tesla-deliveries-miss",
      time: "10h ago",
      category: "earnings",
      tickers: ["TSLA", "RIVN", "NIO"],
      sentiment: "bearish",
    },
    {
      title: "HDFC Bank merger integration completed, cost synergies ahead of plan",
      publisher: "Mint",
      url: "https://finance.yahoo.com/news/hdfc-bank-merger",
      time: "11h ago",
      category: "india",
      tickers: ["HDFCBANK.NS", "KOTAKBANK.NS"],
      sentiment: "bullish",
    },
    {
      title: "Oil prices climb to $88 as Middle East tensions flare",
      publisher: "Reuters",
      url: "https://finance.yahoo.com/news/oil-prices-middle-east",
      time: "12h ago",
      category: "macro",
      tickers: ["USO", "XLE", "CVX"],
      sentiment: "bearish",
    },
    {
      title: "Insider buying spikes at regional banks post-SVB anniversary",
      publisher: "MarketWatch",
      url: "https://finance.yahoo.com/news/regional-banks-insider-buying",
      time: "14h ago",
      category: "insider",
      tickers: ["PNFP", "TFC", "ZION"],
      sentiment: "bullish",
    },
  ],
  trending: [
    "NVIDIA",
    "Fed Rates",
    "TCS",
    "AI Chips",
    "India GDP",
    "Tesla",
    "Oil",
    "HDFC Bank",
  ],
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function sentimentIcon(s: NewsDeskItem["sentiment"]) {
  if (s === "bullish") return <TrendingUp size={14} className="text-tertiary" />;
  if (s === "bearish") return <TrendingDown size={14} className="text-error" />;
  return <Minus size={14} className="text-on-surface-variant" />;
}

function sentimentClass(s: NewsDeskItem["sentiment"]) {
  if (s === "bullish") return "bg-tertiary/10 text-tertiary border-tertiary/20";
  if (s === "bearish") return "bg-error/10 text-error border-error/20";
  return "bg-surface-high text-on-surface-variant border-ghost-border";
}

function categoryLabel(c: NewsDeskItem["category"]) {
  return CATEGORIES.find((x) => x.key === c)?.label ?? c;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function SentimentBadge({ sentiment }: { sentiment: NewsDeskResponse["sentiment"] }) {
  const config = {
    bullish: {
      icon: TrendingUp,
      label: "Bullish",
      class: "bg-tertiary/10 text-tertiary border-tertiary/20",
      pulse: "animate-pulse-glow",
    },
    bearish: {
      icon: TrendingDown,
      label: "Bearish",
      class: "bg-error/10 text-error border-error/20",
      pulse: "",
    },
    neutral: {
      icon: Minus,
      label: "Neutral",
      class: "bg-surface-high text-on-surface-variant border-ghost-border",
      pulse: "",
    },
  }[sentiment];

  const Icon = config.icon;

  return (
    <div
      className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium ${config.class} ${config.pulse}`}
    >
      <Icon size={16} />
      <span>Market Sentiment: {config.label}</span>
    </div>
  );
}

function NewsCard({ item }: { item: NewsDeskItem }) {
  return (
    <GhostBorderCard hover className="transition-all">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0 space-y-2">
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="group block"
          >
            <h3 className="text-sm font-semibold text-on-surface leading-snug group-hover:text-primary transition-colors">
              {item.title}
            </h3>
          </a>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-primary font-medium">{item.publisher}</span>
            <span className="text-[10px] text-on-surface-variant flex items-center gap-1">
              <Clock size={10} />
              {item.time}
            </span>
            <span
              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${sentimentClass(
                item.sentiment
              )}`}
            >
              {sentimentIcon(item.sentiment)}
              {item.sentiment.charAt(0).toUpperCase() + item.sentiment.slice(1)}
            </span>
            <span className="rounded bg-surface-high px-1.5 py-0.5 text-[10px] text-on-surface-variant">
              {categoryLabel(item.category)}
            </span>
          </div>

          {item.tickers.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-0.5">
              {item.tickers.map((ticker) => (
                <Link
                  key={ticker}
                  href={`/stocks/${ticker}`}
                  className="inline-flex items-center gap-0.5 rounded-md bg-surface-high px-1.5 py-0.5 text-[10px] font-medium text-on-surface-variant hover:text-primary hover:bg-surface-highest transition-colors"
                >
                  <ArrowUpRight size={10} />
                  {ticker}
                </Link>
              ))}
            </div>
          )}
        </div>

        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-0.5 shrink-0 text-on-surface-variant hover:text-primary transition-colors"
          aria-label="Open article"
        >
          <ExternalLink size={14} />
        </a>
      </div>
    </GhostBorderCard>
  );
}

function TrendingSidebar({ topics }: { topics: string[] }) {
  return (
    <GhostBorderCard>
      <div className="flex items-center gap-2 pb-3 border-b border-ghost-border">
        <Radio size={14} className="text-secondary" />
        <h2 className="font-headline text-sm font-semibold text-on-surface">
          Trending Topics
        </h2>
      </div>

      <div className="flex flex-wrap gap-2 pt-3">
        {topics.map((topic, i) => (
          <span
            key={topic}
            className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium border transition-colors ${
              i < 3
                ? "bg-primary/10 text-primary border-primary/20"
                : "bg-surface-high text-on-surface-variant border-ghost-border hover:text-on-surface hover:bg-surface-highest"
            }`}
          >
            {i < 3 && <span className="mr-1 h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />}
            {topic}
          </span>
        ))}
      </div>
    </GhostBorderCard>
  );
}

function CategoryStats({ headlines }: { headlines: NewsDeskItem[] }) {
  const stats = useMemo(() => {
    const total = headlines.length;
    const bullish = headlines.filter((h) => h.sentiment === "bullish").length;
    const bearish = headlines.filter((h) => h.sentiment === "bearish").length;
    return { total, bullish, bearish };
  }, [headlines]);

  return (
    <GhostBorderCard>
      <div className="flex items-center gap-2 pb-3 border-b border-ghost-border">
        <Newspaper size={14} className="text-primary" />
        <h2 className="font-headline text-sm font-semibold text-on-surface">
          Feed Stats
        </h2>
      </div>
      <div className="grid grid-cols-3 gap-2 pt-3">
        <div className="rounded-lg bg-surface-high p-2 text-center">
          <div className="text-lg font-bold text-on-surface">{stats.total}</div>
          <div className="text-[10px] text-on-surface-variant uppercase tracking-wide">Headlines</div>
        </div>
        <div className="rounded-lg bg-tertiary/10 p-2 text-center border border-tertiary/20">
          <div className="text-lg font-bold text-tertiary">{stats.bullish}</div>
          <div className="text-[10px] text-tertiary/80 uppercase tracking-wide">Bullish</div>
        </div>
        <div className="rounded-lg bg-error/10 p-2 text-center border border-error/20">
          <div className="text-lg font-bold text-error">{stats.bearish}</div>
          <div className="text-[10px] text-error/80 uppercase tracking-wide">Bearish</div>
        </div>
      </div>
    </GhostBorderCard>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function NewsDeskPage() {
  const [data, setData] = useState<NewsDeskResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [activeCategory, setActiveCategory] = useState<NewsDeskItem["category"] | "all">("all");

  useEffect(() => {
    api
      .getNewsDesk()
      .then((d) => {
        setData(d);
        setError(false);
      })
      .catch((e) => {
        console.warn("NewsDesk API failed, falling back to mock data:", e);
        setData(MOCK_NEWS);
        setError(true);
      })
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    if (!data) return [];
    if (activeCategory === "all") return data.headlines;
    return data.headlines.filter((h) => h.category === activeCategory);
  }, [data, activeCategory]);

  return (
    <div className="space-y-5 p-4 lg:p-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-headline text-2xl font-bold text-on-surface">
            NewsDesk
          </h1>
          <p className="text-sm text-on-surface-variant">
            Real-time market intelligence feed
          </p>
        </div>
        <SentimentBadge sentiment={data?.sentiment ?? "neutral"} />
      </div>

      {/* Category Filters */}
      <GlassPanel>
        <div className="flex flex-wrap gap-2">
          {CATEGORIES.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setActiveCategory(key)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                activeCategory === key
                  ? "bg-surface-high text-on-surface border border-ghost-border"
                  : "text-on-surface-variant hover:bg-surface-high hover:text-on-surface"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </GlassPanel>

      {/* Error fallback notice */}
      {error && (
        <div className="rounded-lg bg-primary/10 border border-primary/20 px-3 py-2 text-xs text-primary">
          API endpoint unavailable — showing demo headlines.
        </div>
      )}

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-5">
        {/* Main Feed */}
        <div className="space-y-3">
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <div
                  key={i}
                  className="h-[88px] rounded-xl bg-surface-container animate-pulse"
                />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <GhostBorderCard className="text-center py-12">
              <Newspaper size={24} className="mx-auto text-on-surface-variant mb-2" />
              <p className="text-sm text-on-surface-variant">
                No headlines in this category.
              </p>
            </GhostBorderCard>
          ) : (
            <div className="space-y-3">
              {filtered.map((item, idx) => (
                <div key={idx} className="animate-fade-in" style={{ animationDelay: `${idx * 40}ms` }}>
                  <NewsCard item={item} />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-5">
          <TrendingSidebar topics={data?.trending ?? []} />
          {!loading && data && <CategoryStats headlines={data.headlines} />}
        </div>
      </div>
    </div>
  );
}

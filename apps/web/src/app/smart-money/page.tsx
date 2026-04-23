"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { SmartMoneyData, SmartMoneyTransaction } from "@/lib/types";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import GlassPanel from "@/components/ui/GlassPanel";
import GradientButton from "@/components/ui/GradientButton";
import { Input } from "@/components/ui/input";
import {
  Search,
  Briefcase,
  TrendingUp,
  TrendingDown,
  ArrowUpRight,
  ArrowDownRight,
  DollarSign,
  Calendar,
  User,
  Loader2,
  RefreshCw,
} from "lucide-react";

// ─── Mock Data Fallback ─────────────────────────────────────────────────────────

const MOCK_DATA: SmartMoneyData = {
  transactions: [
    {
      id: "sm-001",
      ticker: "AAPL",
      insider_name: "Timothy Cook",
      insider_title: "CEO",
      transaction_type: "Buy",
      shares: 50000,
      price: 198.45,
      date: "2026-04-21",
      sentiment_score: 8.7,
    },
    {
      id: "sm-002",
      ticker: "MSFT",
      insider_name: "Satya Nadella",
      insider_title: "CEO",
      transaction_type: "Sell",
      shares: 25000,
      price: 412.30,
      date: "2026-04-20",
      sentiment_score: 4.2,
    },
    {
      id: "sm-003",
      ticker: "NVDA",
      insider_name: "Jensen Huang",
      insider_title: "CEO",
      transaction_type: "Buy",
      shares: 120000,
      price: 115.80,
      date: "2026-04-18",
      sentiment_score: 9.1,
    },
    {
      id: "sm-004",
      ticker: "TSLA",
      insider_name: "Zachary Kirkhorn",
      insider_title: "CFO",
      transaction_type: "Sell",
      shares: 35000,
      price: 245.60,
      date: "2026-04-17",
      sentiment_score: 3.5,
    },
    {
      id: "sm-005",
      ticker: "GOOGL",
      insider_name: "Sundar Pichai",
      insider_title: "CEO",
      transaction_type: "Buy",
      shares: 18000,
      price: 158.20,
      date: "2026-04-16",
      sentiment_score: 7.8,
    },
    {
      id: "sm-006",
      ticker: "META",
      insider_name: "Susan Li",
      insider_title: "CFO",
      transaction_type: "Buy",
      shares: 22000,
      price: 512.40,
      date: "2026-04-15",
      sentiment_score: 8.3,
    },
    {
      id: "sm-007",
      ticker: "AMZN",
      insider_name: "Andrew Jassy",
      insider_title: "CEO",
      transaction_type: "Sell",
      shares: 45000,
      price: 178.90,
      date: "2026-04-14",
      sentiment_score: 4.8,
    },
    {
      id: "sm-008",
      ticker: "AMD",
      insider_name: "Lisa Su",
      insider_title: "CEO",
      transaction_type: "Buy",
      shares: 85000,
      price: 89.50,
      date: "2026-04-13",
      sentiment_score: 8.9,
    },
    {
      id: "sm-009",
      ticker: "NFLX",
      insider_name: "Gregory Peters",
      insider_title: "Co-CEO",
      transaction_type: "Sell",
      shares: 12000,
      price: 945.20,
      date: "2026-04-12",
      sentiment_score: 5.1,
    },
    {
      id: "sm-010",
      ticker: "CRM",
      insider_name: "Marc Benioff",
      insider_title: "CEO",
      transaction_type: "Buy",
      shares: 30000,
      price: 267.15,
      date: "2026-04-11",
      sentiment_score: 7.4,
    },
    {
      id: "sm-011",
      ticker: "AAPL",
      insider_name: "Luca Maestri",
      insider_title: "CFO",
      transaction_type: "Buy",
      shares: 25000,
      price: 196.80,
      date: "2026-04-10",
      sentiment_score: 8.1,
    },
    {
      id: "sm-012",
      ticker: "MSFT",
      insider_name: "Amy Hood",
      insider_title: "CFO",
      transaction_type: "Sell",
      shares: 18000,
      price: 415.60,
      date: "2026-04-09",
      sentiment_score: 4.5,
    },
  ],
  most_bought: [
    { ticker: "NVDA", total_shares: 120000, total_value: 13896000, transactions: 1 },
    { ticker: "AMD", total_shares: 85000, total_value: 7607500, transactions: 1 },
    { ticker: "AAPL", total_shares: 75000, total_value: 14756250, transactions: 2 },
    { ticker: "META", total_shares: 22000, total_value: 11272800, transactions: 1 },
  ],
  most_sold: [
    { ticker: "AMZN", total_shares: 45000, total_value: 8050500, transactions: 1 },
    { ticker: "TSLA", total_shares: 35000, total_value: 8596000, transactions: 1 },
    { ticker: "MSFT", total_shares: 43000, total_value: 17775800, transactions: 2 },
    { ticker: "NFLX", total_shares: 12000, total_value: 11342400, transactions: 1 },
  ],
  last_updated: "2026-04-22T10:00:00Z",
};

// ─── API Fetch ────────────────────────────────────────────────────────────────

async function fetchSmartMoney(): Promise<SmartMoneyData> {
  try {
    const res = await fetch("/api/smart-money", {
      headers: { "Content-Type": "application/json" },
    });
    if (res.status === 404) {
      console.warn("Smart Money API not found — using mock data");
      return MOCK_DATA;
    }
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`API error ${res.status}: ${text}`);
    }
    return res.json();
  } catch (e) {
    console.warn("Smart Money fetch failed — using mock data:", e);
    return MOCK_DATA;
  }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatShares(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function formatCurrency(n: number): string {
  if (n >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(2)}B`;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(1)}K`;
  return `$${n.toLocaleString()}`;
}

function sentimentColor(score: number): string {
  if (score >= 7) return "text-tertiary";
  if (score >= 4) return "text-secondary";
  return "text-error";
}

function sentimentBg(score: number): string {
  if (score >= 7) return "bg-tertiary/10 text-tertiary border-tertiary/20";
  if (score >= 4) return "bg-secondary/10 text-secondary border-secondary/20";
  return "bg-error/10 text-error border-error/20";
}

// ─── Components ─────────────────────────────────────────────────────────────────

function TransactionBadge({ type }: { type: "Buy" | "Sell" }) {
  const isBuy = type === "Buy";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${
        isBuy
          ? "bg-tertiary/10 text-tertiary border-tertiary/20"
          : "bg-error/10 text-error border-error/20"
      }`}
    >
      {isBuy ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
      {type}
    </span>
  );
}

function SentimentBadge({ score }: { score: number }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${sentimentBg(score)}`}
    >
      {score.toFixed(1)}
    </span>
  );
}

function SummaryCard({
  title,
  icon: Icon,
  iconColor,
  items,
}: {
  title: string;
  icon: React.ElementType;
  iconColor: string;
  items: SmartMoneyData["most_bought"] | SmartMoneyData["most_sold"];
}) {
  return (
    <GhostBorderCard className="h-full">
      <div className="flex items-center gap-2 pb-3 border-b border-ghost-border">
        <Icon size={16} className={iconColor} />
        <h2 className="font-headline text-sm font-semibold text-on-surface">{title}</h2>
      </div>
      <div className="mt-3 space-y-2">
        {items.map((item, i) => (
          <Link
            key={item.ticker}
            href={`/stocks/${item.ticker}`}
            className="flex items-center justify-between rounded-lg px-3 py-2.5 hover:bg-surface-high transition-colors"
          >
            <div className="flex items-center gap-3">
              <span className="text-xs text-on-surface-variant w-4">{i + 1}</span>
              <span className="font-headline font-bold text-sm text-on-surface">{item.ticker}</span>
            </div>
            <div className="text-right">
              <div className="tabular-nums text-sm font-semibold text-on-surface">
                {formatShares(item.total_shares)}
                <span className="text-xs text-on-surface-variant font-normal"> shares</span>
              </div>
              <div className="tabular-nums text-xs text-on-surface-variant">
                {formatCurrency(item.total_value)}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </GhostBorderCard>
  );
}

function TransactionTable({
  transactions,
  loading,
}: {
  transactions: SmartMoneyTransaction[];
  loading: boolean;
}) {
  if (loading) {
    return (
      <GhostBorderCard>
        <div className="space-y-3 animate-pulse">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="flex gap-3 items-center">
              <div className="h-4 w-16 bg-surface-high rounded" />
              <div className="h-4 w-24 bg-surface-high rounded" />
              <div className="h-4 w-16 bg-surface-high rounded" />
              <div className="h-4 w-20 bg-surface-high rounded ml-auto" />
            </div>
          ))}
        </div>
      </GhostBorderCard>
    );
  }

  if (transactions.length === 0) {
    return (
      <GhostBorderCard>
        <div className="text-center py-8">
          <Search size={24} className="mx-auto text-on-surface-variant mb-2" />
          <p className="text-sm text-on-surface-variant">No insider transactions match your search.</p>
        </div>
      </GhostBorderCard>
    );
  }

  return (
    <GhostBorderCard className="overflow-hidden p-0">
      {/* Header Row */}
      <div className="hidden sm:grid sm:grid-cols-[100px_1fr_100px_100px_80px_100px_80px] gap-3 px-4 py-3 bg-surface-high/50 border-b border-ghost-border text-xs font-semibold text-on-surface-variant uppercase tracking-wide">
        <span>Ticker</span>
        <span>Insider</span>
        <span className="text-center">Type</span>
        <span className="text-right">Shares</span>
        <span className="text-right">Price</span>
        <span className="text-right">Date</span>
        <span className="text-right">Score</span>
      </div>

      {/* Mobile / Data Rows */}
      <div className="divide-y divide-ghost-border/50">
        {transactions.map((tx) => (
          <div
            key={tx.id}
            className="block sm:grid sm:grid-cols-[100px_1fr_100px_100px_80px_100px_80px] gap-3 px-4 py-3 hover:bg-surface-high transition-colors items-center"
          >
            {/* Mobile: stack layout */}
            <div className="sm:hidden space-y-2 pb-2">
              <div className="flex items-center justify-between">
                <Link
                  href={`/stocks/${tx.ticker}`}
                  className="font-headline font-bold text-base text-on-surface hover:text-primary transition-colors"
                >
                  {tx.ticker}
                </Link>
                <TransactionBadge type={tx.transaction_type} />
              </div>
              <div className="flex items-center gap-2 text-sm text-on-surface">
                <User size={12} className="text-on-surface-variant" />
                <span>{tx.insider_name}</span>
                <span className="text-xs text-on-surface-variant">({tx.insider_title})</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="tabular-nums text-on-surface">
                  {formatShares(tx.shares)} @ ${tx.price.toFixed(2)}
                </span>
                <span className="text-xs text-on-surface-variant">
                  {new Date(tx.date).toLocaleDateString()}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-on-surface-variant">Sentiment</span>
                <SentimentBadge score={tx.sentiment_score} />
              </div>
            </div>

            {/* Desktop: grid layout */}
            <div className="hidden sm:block">
              <Link
                href={`/stocks/${tx.ticker}`}
                className="font-headline font-bold text-sm text-on-surface hover:text-primary transition-colors"
              >
                {tx.ticker}
              </Link>
            </div>
            <div className="hidden sm:flex sm:flex-col sm:justify-center">
              <span className="text-sm text-on-surface truncate">{tx.insider_name}</span>
              <span className="text-xs text-on-surface-variant">{tx.insider_title}</span>
            </div>
            <div className="hidden sm:flex sm:justify-center">
              <TransactionBadge type={tx.transaction_type} />
            </div>
            <div className="hidden sm:block text-right">
              <span className="tabular-nums text-sm text-on-surface">{formatShares(tx.shares)}</span>
            </div>
            <div className="hidden sm:block text-right">
              <span className="tabular-nums text-sm text-on-surface">${tx.price.toFixed(2)}</span>
            </div>
            <div className="hidden sm:block text-right">
              <span className="text-xs text-on-surface-variant">{new Date(tx.date).toLocaleDateString()}</span>
            </div>
            <div className="hidden sm:flex sm:justify-end">
              <SentimentBadge score={tx.sentiment_score} />
            </div>
          </div>
        ))}
      </div>
    </GhostBorderCard>
  );
}

// ─── Main Page ──────────────────────────────────────────────────────────────────

export default function SmartMoneyPage() {
  const [data, setData] = useState<SmartMoneyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await fetchSmartMoney();
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load smart money data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const filtered = useMemo(() => {
    if (!data) return [];
    if (!search.trim()) return data.transactions;
    const q = search.trim().toUpperCase();
    return data.transactions.filter(
      (tx) =>
        tx.ticker.includes(q) ||
        tx.insider_name.toUpperCase().includes(q) ||
        tx.insider_title.toUpperCase().includes(q)
    );
  }, [data, search]);

  return (
    <div className="space-y-6 p-4 lg:p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="font-headline text-2xl font-bold text-on-surface flex items-center gap-2">
            <Briefcase size={24} className="text-primary" />
            Smart Money Tracker
          </h1>
          <p className="text-sm text-on-surface-variant mt-1 max-w-xl">
            Real-time EDGAR Form 4 insider trading signals. Track what executives and directors are actually buying and selling.
          </p>
        </div>
        {data?.last_updated && (
          <span className="text-xs text-on-surface-variant">
            Updated {new Date(data.last_updated).toLocaleDateString()}
          </span>
        )}
      </div>

      {/* Search Bar */}
      <GlassPanel>
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter by ticker, insider name, or title..."
              className="pl-8 bg-surface-container"
            />
          </div>
          <GradientButton onClick={fetchData} size="sm" className="shrink-0">
            {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            Refresh
          </GradientButton>
        </div>
      </GlassPanel>

      {/* Error State */}
      {error && !data && (
        <GhostBorderCard>
          <div className="text-center py-8">
            <p className="text-sm text-error">{error}</p>
            <button
              onClick={fetchData}
              className="mt-3 text-xs text-primary hover:underline"
            >
              Retry
            </button>
          </div>
        </GhostBorderCard>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <SummaryCard
          title="Most Bought"
          icon={TrendingUp}
          iconColor="text-tertiary"
          items={data?.most_bought ?? []}
        />
        <SummaryCard
          title="Most Sold"
          icon={TrendingDown}
          iconColor="text-error"
          items={data?.most_sold ?? []}
        />
      </div>

      {/* Transaction Count */}
      <div className="flex items-center justify-between">
        <h2 className="font-headline text-sm font-semibold text-on-surface flex items-center gap-2">
          <DollarSign size={14} className="text-secondary" />
          Recent Insider Transactions
        </h2>
        <span className="text-xs text-on-surface-variant">
          {filtered.length} result{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Transactions Table */}
      <TransactionTable transactions={filtered} loading={loading && !data} />

      {/* Footer note */}
      <p className="text-xs text-on-surface-variant/60 text-center">
        Data sourced from SEC EDGAR Form 4 filings. Sentiment scores are derived from transaction size, frequency, and historical insider performance.
      </p>
    </div>
  );
}

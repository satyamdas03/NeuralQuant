"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import GhostBorderCard from "./GhostBorderCard";
import { TrendingUp, ArrowUpRight, ArrowDownRight, Sun, Star } from "lucide-react";

interface WrapIndex {
  name: string;
  price: number;
  change_pct: number;
}

interface WrapPick {
  ticker: string;
  composite_score?: number;
  score_1_10?: number;
  sector?: string;
}

interface WrapData {
  date: string;
  market: string;
  market_label: string;
  indices: WrapIndex[];
  top_picks: WrapPick[];
  watchlist_picks?: WrapPick[];
}

export default function MarketWrapCard() {
  const [tab, setTab] = useState<"US" | "IN">("US");
  const [data, setData] = useState<Record<string, WrapData | null>>({ US: null, IN: null });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (data[tab]) return;
    let cancelled = false;
    setLoading(true);
    apiFetch<WrapData>(`/market-wrap/today?market=${tab}`)
      .then((d) => { if (!cancelled) setData((p) => ({ ...p, [tab]: d })); })
      .catch(() => { if (!cancelled) setData((p) => ({ ...p, [tab]: null as WrapData | null })); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const wrap = data[tab];

  return (
    <GhostBorderCard>
      <div className="flex items-center justify-between pb-3 border-b border-ghost-border">
        <div className="flex items-center gap-2">
          <Sun size={14} className="text-amber-400" />
          <h2 className="font-headline text-sm font-semibold text-on-surface">
            Daily Market Wrap
          </h2>
        </div>
        <div className="flex rounded-lg border border-ghost-border overflow-hidden">
          {(["US", "IN"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setTab(m)}
              className={`px-3 py-1 text-[10px] font-semibold uppercase tracking-wide transition-colors ${
                tab === m
                  ? "bg-primary/20 text-primary"
                  : "text-on-surface-variant hover:text-on-surface"
              }`}
            >
              {m === "US" ? "S&P 500" : "NIFTY 500"}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="space-y-3 p-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex justify-between">
              <div className="h-4 w-24 bg-surface-high rounded animate-pulse" />
              <div className="h-4 w-16 bg-surface-high rounded animate-pulse" />
            </div>
          ))}
        </div>
      ) : !wrap || !wrap.indices.length ? (
        <p className="py-6 text-center text-xs text-on-surface-variant">
          Market wrap unavailable. Backend may be offline.
        </p>
      ) : (
        <>
          <p className="px-4 pt-3 text-[11px] text-on-surface-variant">
            {wrap.date}
          </p>
          <div className="divide-y divide-ghost-border/50">
            {wrap.indices.map((idx) => (
              <div key={idx.name} className="flex items-center justify-between px-4 py-2.5">
                <span className="text-sm text-on-surface">{idx.name}</span>
                <div className="flex items-center gap-3">
                  <span className="tabular-nums text-sm text-on-surface-variant">
                    {tab === "IN" ? "Rs." : "$"}
                    {idx.price?.toLocaleString() ?? "N/A"}
                  </span>
                  <span
                    className={`flex items-center gap-1 tabular-nums text-sm font-semibold ${
                      idx.change_pct >= 0 ? "text-tertiary" : "text-error"
                    }`}
                  >
                    {idx.change_pct >= 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                    {idx.change_pct >= 0 ? "+" : ""}
                    {idx.change_pct?.toFixed(2) ?? "0.00"}%
                  </span>
                </div>
              </div>
            ))}
          </div>

          {wrap.watchlist_picks && wrap.watchlist_picks.length > 0 && (
            <div className="mt-2 px-4 pb-2">
              <div className="flex items-center gap-1 pb-2 text-[10px] text-on-surface-variant">
                <Star size={10} className="text-amber-400"/>
                Your Watchlist
              </div>
              <div className="flex flex-wrap gap-1.5">
                {wrap.watchlist_picks.map((p) => (
                  <Link
                    key={p.ticker}
                    href={`/stocks/${p.ticker}?market=${tab}`}
                    className="inline-flex items-center gap-1.5 rounded-full bg-amber-400/10 border border-amber-400/30 px-3 py-1 text-xs font-medium text-on-surface hover:border-amber-400/60 transition-colors"
                  >
                    {p.ticker}
                    <span className="font-bold text-amber-400">
                      {p.score_1_10 || (p.composite_score ? (p.composite_score * 10).toFixed(0) : "?")}/10
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {wrap.top_picks.length > 0 && (
            <div className="mt-2 px-4 pb-4">
              <div className="flex items-center gap-1 pb-2 text-[10px] text-on-surface-variant">
                <TrendingUp size={10} className="text-primary-fixed"/>
                Top QuantAlpha Picks
              </div>
              <div className="flex flex-wrap gap-1.5">
                {wrap.top_picks.map((p) => (
                  <Link
                    key={p.ticker}
                    href={`/stocks/${p.ticker}?market=${tab}`}
                    className="inline-flex items-center gap-1.5 rounded-full bg-surface-high border border-ghost-border px-3 py-1 text-xs font-medium text-on-surface hover:border-primary/40 transition-colors"
                  >
                    {p.ticker}
                    <span className="font-bold text-primary">
                      {p.score_1_10 || (p.composite_score ? (p.composite_score * 10).toFixed(0) : "?")}/10
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </GhostBorderCard>
  );
}

async function apiFetch<T>(path: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  try {
    const { createClient } = await import("@/lib/supabase/client");
    const supabase = createClient();
    const { data } = await supabase.auth.getSession();
    if (data.session?.access_token) {
      headers["Authorization"] = `Bearer ${data.session.access_token}`;
    }
  } catch {
    // Guest — no auth header
  }
  const response = await fetch(`/api${path}`, { headers });
  if (!response.ok) throw new Error(`API ${response.status}`);
  return response.json();
}

"use client";

import { useEffect, useState } from "react";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import { MessageSquare, Hash } from "lucide-react";

interface SocialData {
  ticker: string;
  reddit_bullish_pct: number | null;
  reddit_mentions: number;
  stocktwits_bullish_pct: number | null;
  stocktwits_mentions: number;
  total_mentions: number;
  topics: string[];
  loading?: boolean;
}

export default function SocialBuzzCard() {
  const [data, setData] = useState<SocialData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/sentiment/social`)
      .then((r) => r.json())
      .then((d) => {
        const items: SocialData[] = d.tickers || [];
        // If all items are loading placeholders, keep loading state
        if (items.length > 0 && items.every((i) => i.loading)) {
          setLoading(true);
          // Retry after a short delay for background fetch to complete
          setTimeout(() => {
            fetch(`/api/sentiment/social`)
              .then((r2) => r2.json())
              .then((d2) => {
                setData(d2.tickers || []);
                setLoading(false);
              })
              .catch(() => setLoading(false));
          }, 8000);
          return;
        }
        setData(items);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <GhostBorderCard>
        <p className="text-xs text-on-surface-variant">Loading social buzz...</p>
      </GhostBorderCard>
    );
  }

  // Filter out loading placeholders
  const realData = data.filter((d) => !d.loading);

  if (!realData.length) {
    return (
      <GhostBorderCard>
        <p className="text-xs text-on-surface-variant">Social sentiment unavailable</p>
      </GhostBorderCard>
    );
  }

  const topMentioned = [...realData].sort((a, b) => b.total_mentions - a.total_mentions).slice(0, 5);

  return (
    <GhostBorderCard>
      <div className="flex items-center gap-2 mb-3">
        <MessageSquare size={16} className="text-secondary" />
        <h3 className="font-semibold text-sm text-on-surface">Social Buzz</h3>
      </div>
      <div className="space-y-2">
        {topMentioned.map((item) => {
          const bullishPct = item.reddit_bullish_pct ?? item.stocktwits_bullish_pct ?? 50;
          const isBullish = bullishPct > 55;
          const isBearish = bullishPct < 45;
          return (
            <div key={item.ticker} className="flex items-center justify-between py-1">
              <span className="text-sm font-medium text-on-surface">{item.ticker}</span>
              <div className="flex items-center gap-3">
                {item.reddit_mentions > 0 && (
                  <span className="text-[10px] text-on-surface-variant flex items-center gap-0.5">
                    <MessageSquare size={10} /> {item.reddit_mentions}
                  </span>
                )}
                {item.stocktwits_mentions > 0 && (
                  <span className="text-[10px] text-on-surface-variant flex items-center gap-0.5">
                    <Hash size={10} /> {item.stocktwits_mentions}
                  </span>
                )}
                <span className={`text-xs font-medium ${isBullish ? "text-tertiary" : isBearish ? "text-error" : "text-on-surface-variant"}`}>
                  {isBullish ? "↑" : isBearish ? "↓" : "→"} {bullishPct}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </GhostBorderCard>
  );
}
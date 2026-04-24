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
  trending_topics: string[];
}

export default function SocialBuzzCard() {
  const [data, setData] = useState<SocialData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/sentiment/social`)
      .then((r) => r.json())
      .then((d) => {
        setData(d.sentiment || []);
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

  if (!data.length) {
    return (
      <GhostBorderCard>
        <p className="text-xs text-on-surface-variant">Social sentiment unavailable</p>
      </GhostBorderCard>
    );
  }

  const topMentioned = [...data].sort((a, b) => b.total_mentions - a.total_mentions).slice(0, 5);

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
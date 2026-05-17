"use client";

import { useEffect, useState } from "react";
import type { IndexData } from "@/lib/types";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";

const TICKER_ORDER = [
  "S&P 500", "NASDAQ", "Dow Jones", "VIX",
  "NIFTY 50", "SENSEX", "INDIA VIX", "USD/INR",
];

export default function MarketTicker() {
  const [indices, setIndices] = useState<IndexData[]>([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/market/overview")
      .then((r) => { if (!r.ok) throw new Error(""); return r.json(); })
      .then((d) => {
        if (!cancelled && d.indices) {
          // Sort in preferred display order
          const ordered = [...(d.indices as IndexData[])].sort((a, b) => {
            const ai = TICKER_ORDER.indexOf(a.name);
            const bi = TICKER_ORDER.indexOf(b.name);
            if (ai === -1 && bi === -1) return 0;
            if (ai === -1) return 1;
            if (bi === -1) return -1;
            return ai - bi;
          });
          setIndices(ordered);
        }
      })
      .catch(() => { if (!cancelled) setError(true); });
    // Refresh every 5 minutes
    const interval = setInterval(() => {
      fetch("/api/market/overview")
        .then((r) => r.json())
        .then((d) => { if (d.indices) setIndices(d.indices); })
        .catch(() => {});
    }, 300_000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  if (error || !indices.length) {
    return (
      <div className="fixed top-[80px] w-full h-10 bg-surface border-b border-border-glow overflow-hidden flex items-center z-40">
        <div className="flex whitespace-nowrap animate-[scroll_30s_linear_infinite] items-center">
          <div className="flex items-center font-mono text-[11px] tracking-[0.1em] px-6 text-text-muted">
            Market data loading…
          </div>
        </div>
      </div>
    );
  }

  const items = TICKER_ORDER
    .map((name) => indices.find((i) => i.name === name))
    .filter((i): i is IndexData => !!i);

  const renderItem = (item: IndexData, key: string) => {
    const up = item.change_pct >= 0;
    return (
      <div key={key} className="flex items-center gap-2 font-mono text-[11px] tracking-[0.1em] border-r border-border-glow px-6">
        <span className="text-text-primary font-bold">{item.name}</span>
        <span className="text-text-muted tabular-nums">
          {item.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </span>
        <span className={`flex items-center gap-0.5 tabular-nums font-bold ${up ? "text-primary-fixed" : "text-cyber-red"}`}>
          {up ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
          {up ? "+" : ""}{item.change_pct.toFixed(2)}%
        </span>
      </div>
    );
  };

  return (
    <div className="fixed top-[80px] w-full h-10 bg-surface border-b border-border-glow overflow-hidden flex items-center z-40">
      <div className="flex whitespace-nowrap animate-[scroll_30s_linear_infinite] items-center">
        {items.map((item, i) => renderItem(item, `ticker-${i}`))}
        {/* Duplicate for seamless loop */}
        {items.map((item, i) => renderItem(item, `ticker-dup-${i}`))}
      </div>
    </div>
  );
}

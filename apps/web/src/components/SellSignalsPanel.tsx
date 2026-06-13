"use client";

import { useEffect, useState } from "react";
import { authedApi } from "@/lib/api";
import type { SellSignal } from "@/lib/types";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import { AlertTriangle, Loader2 } from "lucide-react";
import Link from "next/link";

export default function SellSignalsPanel({ market = "IN" }: { market?: "US" | "IN" | "GLOBAL" }) {
  const [sellSignals, setSellSignals] = useState<SellSignal[]>([]);
  const [neutralSignals, setNeutralSignals] = useState<SellSignal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    authedApi.getAstraSellSignals(market)
      .then((data) => {
        setSellSignals(Array.isArray(data?.sell_signals) ? data.sell_signals : []);
        setNeutralSignals(Array.isArray(data?.neutral_signals) ? data.neutral_signals : []);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load sell signals"))
      .finally(() => setLoading(false));
  }, [market]);

  if (loading) {
    return (
      <GhostBorderCard>
        <div className="flex items-center justify-center py-6 gap-2">
          <Loader2 size={16} className="animate-spin text-primary" />
          <span className="text-sm text-on-surface-variant">Scanning for sell signals…</span>
        </div>
      </GhostBorderCard>
    );
  }

  if (error) {
    return (
      <GhostBorderCard>
        <div className="text-center py-6">
          <p className="text-sm text-error">{error}</p>
          <button onClick={() => window.location.reload()} className="text-xs text-primary mt-2 hover:underline">Retry</button>
        </div>
      </GhostBorderCard>
    );
  }

  const allSignals = [
    ...sellSignals.map((s) => ({ ...s, severity: "HARD_SELL" as const })),
    ...neutralSignals.map((s) => ({ ...s, severity: "NEUTRAL" as const })),
  ];

  if (allSignals.length === 0) {
    return (
      <GhostBorderCard>
        <div className="text-center py-6">
          <p className="text-sm text-on-surface-variant">No sell signals detected — portfolio looks healthy.</p>
        </div>
      </GhostBorderCard>
    );
  }

  return (
    <div className="space-y-3">
      {/* Hard Sell Section */}
      {sellSignals.length > 0 && (
        <div className="rounded-xl bg-red-500/5 border border-red-500/20 p-4 space-y-3">
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} className="text-red-400" />
            <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-red-400">
              Hard Sell Signals ({sellSignals.length})
            </h3>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {sellSignals.map((s) => (
              <Link
                key={s.ticker}
                href={`/stocks/${s.ticker}?market=${market}`}
                className="block rounded-lg bg-surface-container/60 border border-red-500/15 p-3 hover:border-red-500/40 transition-colors"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-headline text-sm font-bold text-on-surface">{s.ticker}</span>
                  {s.irs_pct != null && (
                    <span className="text-[10px] font-mono font-bold text-red-400">
                      IRS {s.irs_pct.toFixed(0)}%
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-on-surface-variant">{s.reason}</p>
                {s.sector && (
                  <span className="text-[9px] font-mono text-on-surface-variant mt-1 block">{s.sector}</span>
                )}
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Neutral Zone Section */}
      {neutralSignals.length > 0 && (
        <div className="rounded-xl bg-amber-500/5 border border-amber-500/20 p-4 space-y-3">
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} className="text-amber-400" />
            <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-amber-400">
              Caution Zone ({neutralSignals.length})
            </h3>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {neutralSignals.map((s) => (
              <Link
                key={s.ticker}
                href={`/stocks/${s.ticker}?market=${market}`}
                className="block rounded-lg bg-surface-container/60 border border-amber-500/15 p-3 hover:border-amber-500/40 transition-colors"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-headline text-sm font-bold text-on-surface">{s.ticker}</span>
                  {s.irs_pct != null && (
                    <span className="text-[10px] font-mono font-bold text-amber-400">
                      IRS {s.irs_pct.toFixed(0)}%
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-on-surface-variant">{s.reason}</p>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* SEBI Disclaimer */}
      <p className="text-[9px] text-on-surface-variant text-center">
        ⚠️ These are quantitative sell signals, not investment advice. Consult a SEBI-registered advisor.
      </p>
    </div>
  );
}
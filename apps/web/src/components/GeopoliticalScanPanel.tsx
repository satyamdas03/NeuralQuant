"use client";

import { useEffect, useState } from "react";
import { authedApi } from "@/lib/api";
import type { GeopoliticalWarning } from "@/lib/types";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import { Globe, Loader2 } from "lucide-react";
import Link from "next/link";

function riskStyles(level: "HIGH" | "MEDIUM") {
  return level === "HIGH"
    ? "bg-red-500/5 border-red-500/20"
    : "bg-amber-500/5 border-amber-500/20";
}

function riskBadge(level: "HIGH" | "MEDIUM") {
  const cls =
    level === "HIGH"
      ? "bg-red-500/15 text-red-400 border-red-500/30"
      : "bg-amber-500/15 text-amber-400 border-amber-500/30";
  return (
    <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${cls}`}>
      {level}
    </span>
  );
}

export default function GeopoliticalScanPanel({ market = "IN" }: { market?: "US" | "IN" | "GLOBAL" }) {
  const [warnings, setWarnings] = useState<GeopoliticalWarning[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalScanned, setTotalScanned] = useState(0);

  useEffect(() => {
    authedApi.getAstraGeopoliticalScan(market)
      .then((data) => {
        setWarnings(Array.isArray(data?.warnings) ? data.warnings : []);
        setTotalScanned(data?.total_scanned ?? 0);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Scan failed"))
      .finally(() => setLoading(false));
  }, [market]);

  if (loading) {
    return (
      <GhostBorderCard>
        <div className="flex items-center justify-center py-6 gap-2">
          <Loader2 size={16} className="animate-spin text-primary" />
          <span className="text-sm text-on-surface-variant">Scanning geopolitical risks…</span>
        </div>
      </GhostBorderCard>
    );
  }

  if (error) {
    return (
      <GhostBorderCard>
        <div className="text-center py-6">
          <p className="text-sm text-error">{error}</p>
        </div>
      </GhostBorderCard>
    );
  }

  if (warnings.length === 0) {
    return (
      <GhostBorderCard>
        <div className="text-center py-6">
          <Globe size={24} className="mx-auto text-primary-fixed mb-2" />
          <p className="text-sm text-on-surface-variant">No geopolitical risk warnings detected for your portfolio.</p>
          {totalScanned > 0 && (
            <p className="text-[10px] text-on-surface-variant mt-1">{totalScanned} holdings scanned</p>
          )}
        </div>
      </GhostBorderCard>
    );
  }

  const highCount = warnings.filter((w) => w.risk_level === "HIGH").length;
  const medCount = warnings.filter((w) => w.risk_level === "MEDIUM").length;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Globe size={16} className="text-primary-fixed" />
          <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-on-surface">
            Geopolitical Risk Scan
          </h3>
        </div>
        <div className="flex items-center gap-2">
          {highCount > 0 && (
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-red-500/15 text-red-400 border border-red-500/30">
              {highCount} HIGH
            </span>
          )}
          {medCount > 0 && (
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30">
              {medCount} MEDIUM
            </span>
          )}
        </div>
      </div>

      <div className="space-y-2">
        {warnings.map((w, i) => (
          <Link
            key={`${w.ticker}-${i}`}
            href={`/stocks/${w.ticker}?market=${market}`}
            className={`block rounded-lg ghost-border p-3 space-y-1.5 ${riskStyles(w.risk_level)}`}
          >
            <div className="flex items-center justify-between">
              <span className="font-headline text-sm font-bold text-on-surface">{w.ticker}</span>
              {riskBadge(w.risk_level)}
            </div>
            <div className="flex items-center gap-3 text-[10px] font-mono text-on-surface-variant">
              {w.sector && <span>{w.sector}</span>}
              {w.beta != null && <span>β {w.beta.toFixed(2)}</span>}
              {w.irs_pct != null && <span>IRS {w.irs_pct.toFixed(0)}%</span>}
            </div>
            {w.recommendation && (
              <p className="text-[11px] text-on-surface">{w.recommendation}</p>
            )}
          </Link>
        ))}
      </div>

      <p className="text-[9px] text-on-surface-variant text-center">
        {totalScanned} holdings scanned · Geopolitically sensitive sectors flagged from your watchlist
      </p>
    </div>
  );
}

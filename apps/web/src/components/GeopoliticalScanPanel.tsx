"use client";

import { useEffect, useState } from "react";
import { authedApi } from "@/lib/api";
import type { GeopoliticalWarning } from "@/lib/types";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import { Globe, AlertTriangle, Loader2 } from "lucide-react";

function severityBadge(severity: "HIGH" | "MEDIUM" | "LOW") {
  const colors = {
    HIGH: "bg-red-500/15 text-red-400 border-red-500/30",
    MEDIUM: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    LOW: "bg-primary-fixed/15 text-primary-fixed border-primary-fixed/30",
  };
  return (
    <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${colors[severity]}`}>
      {severity}
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
        setWarnings(data.warnings ?? []);
        setTotalScanned(data.total_scanned ?? 0);
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
            <p className="text-[10px] text-on-surface-variant mt-1">{totalScanned} sectors scanned</p>
          )}
        </div>
      </GhostBorderCard>
    );
  }

  const highCount = warnings.filter((w) => w.severity === "HIGH").length;
  const medCount = warnings.filter((w) => w.severity === "MEDIUM").length;

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
          <div
            key={i}
            className={`rounded-lg ghost-border p-3 space-y-1.5 ${
              w.severity === "HIGH"
                ? "bg-red-500/5 border-red-500/20"
                : w.severity === "MEDIUM"
                ? "bg-amber-500/5 border-amber-500/20"
                : ""
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-on-surface">{w.title}</span>
              {severityBadge(w.severity)}
            </div>
            <p className="text-xs text-on-surface-variant leading-relaxed">{w.description}</p>
            {w.affected_sectors.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {w.affected_sectors.map((s) => (
                  <span key={s} className="text-[9px] font-mono px-1 py-0.5 rounded bg-surface-container text-on-surface-variant">
                    {s}
                  </span>
                ))}
              </div>
            )}
            {w.affected_tickers.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {w.affected_tickers.slice(0, 5).map((t) => (
                  <span key={t} className="text-[9px] font-mono px-1 py-0.5 rounded bg-surface-container-high text-on-surface">
                    {t}
                  </span>
                ))}
                {w.affected_tickers.length > 5 && (
                  <span className="text-[9px] text-on-surface-variant">+{w.affected_tickers.length - 5} more</span>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      <p className="text-[9px] text-on-surface-variant text-center">
        {totalScanned} sectors scanned · Data sourced from market headlines
      </p>
    </div>
  );
}
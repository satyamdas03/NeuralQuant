"use client";

import { useEffect, useState, useCallback } from "react";
import { authedApi } from "@/lib/api";
import type { AstraRiskProfile, AstraRecommendResponse } from "@/lib/types";
import RiskProfilerModal from "@/components/RiskProfilerModal";
import SellSignalsPanel from "@/components/SellSignalsPanel";
import GeopoliticalScanPanel from "@/components/GeopoliticalScanPanel";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import { PieChart, Shield, TrendingUp, Zap, Loader2, AlertTriangle, RefreshCw } from "lucide-react";

const PROFILE_META: Record<AstraRiskProfile, { label: string; desc: string; icon: typeof Shield; color: string; bgColor: string }> = {
  low: {
    label: "Conservative",
    desc: "100% Large-Cap Alpha — IRS% > 65%, stable growth focus",
    icon: Shield,
    color: "text-primary-fixed",
    bgColor: "bg-primary-fixed/15",
  },
  high: {
    label: "Growth",
    desc: "50% Large-Cap + 30% Small-Cap + 20% Micro-Cap",
    icon: TrendingUp,
    color: "text-amber-400",
    bgColor: "bg-amber-500/15",
  },
  very_high: {
    label: "Aggressive",
    desc: "Large-Cap + Small-Cap + Micro-Cap + Turnaround plays",
    icon: Zap,
    color: "text-red-400",
    bgColor: "bg-red-500/15",
  },
};

function PoolSection({ name, allocation, stocks }: { name: string; allocation: number; stocks: AstraRecommendResponse["pools"][0]["stocks"] }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-mono uppercase tracking-wider text-primary">{name}</h4>
        <span className="text-[10px] font-mono text-on-surface-variant">{allocation}% allocation</span>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {stocks.map((s) => {
          const irsColor = s.irs_pct == null ? "text-on-surface-variant"
            : s.irs_pct >= 65 ? "text-primary-fixed"
            : s.irs_pct >= 45 ? "text-amber-400"
            : "text-red-400";
          return (
            <a
              key={s.ticker}
              href={`/stocks/${s.ticker}?market=IN`}
              className="block rounded-lg ghost-border p-3 hover:border-primary-fixed/40 transition-all duration-200"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-headline text-sm font-bold text-on-surface">{s.ticker}</span>
                {s.irs_pct != null && (
                  <span className={`text-[11px] font-mono font-bold ${irsColor}`}>
                    IRS {s.irs_pct.toFixed(0)}%
                  </span>
                )}
              </div>
              {s.name && (
                <p className="text-[10px] text-on-surface-variant truncate">{s.name}</p>
              )}
              <div className="flex items-center gap-3 mt-1.5">
                {s.g_score != null && (
                  <span className="text-[10px] font-mono text-on-surface-variant">
                    G: {s.g_score >= 0 ? "+" : ""}{s.g_score.toFixed(1)}
                  </span>
                )}
                {s.risk_eff_score != null && (
                  <span className="text-[10px] font-mono text-on-surface-variant">
                    Risk: {s.risk_eff_score >= 0 ? "+" : ""}{s.risk_eff_score.toFixed(1)}
                  </span>
                )}
                {s.sector && (
                  <span className="text-[9px] font-mono text-on-surface-variant">{s.sector}</span>
                )}
              </div>
              {s.rationale && (
                <p className="text-[10px] text-on-surface-variant mt-1 line-clamp-2">{s.rationale}</p>
              )}
            </a>
          );
        })}
      </div>
    </div>
  );
}

export default function PortfolioPage() {
  const [riskProfile, setRiskProfile] = useState<AstraRiskProfile | null>(null);
  const [showProfiler, setShowProfiler] = useState(false);
  const [recommendation, setRecommendation] = useState<AstraRecommendResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [market, setMarket] = useState<"IN" | "US">("IN");

  useEffect(() => {
    // Check for saved risk profile
    authedApi.getRiskProfile()
      .then((data) => {
        if (data.risk_profile) {
          setRiskProfile(data.risk_profile);
          loadRecommendation(data.risk_profile);
        } else {
          // Try localStorage as fallback
          try {
            const saved = localStorage.getItem("nq_risk_profile");
            if (saved && ["low", "high", "very_high"].includes(saved)) {
              const profile = saved as AstraRiskProfile;
              setRiskProfile(profile);
              loadRecommendation(profile);
            } else {
              setShowProfiler(true);
              setLoading(false);
            }
          } catch {
            setShowProfiler(true);
            setLoading(false);
          }
        }
      })
      .catch(() => {
        // Not logged in — try localStorage
        try {
          const saved = localStorage.getItem("nq_risk_profile");
          if (saved && ["low", "high", "very_high"].includes(saved)) {
            const profile = saved as AstraRiskProfile;
            setRiskProfile(profile);
            loadRecommendation(profile);
          } else {
            setShowProfiler(true);
            setLoading(false);
          }
        } catch {
          setShowProfiler(true);
          setLoading(false);
        }
      });
  }, []);

  const loadRecommendation = useCallback((profile: AstraRiskProfile) => {
    setLoading(true);
    setError(null);
    authedApi.getAstraRecommend(profile, market)
      .then(setRecommendation)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load recommendations"))
      .finally(() => setLoading(false));
  }, [market]);

  const handleProfileComplete = (profile: AstraRiskProfile) => {
    setRiskProfile(profile);
    setShowProfiler(false);
    try { localStorage.setItem("nq_risk_profile", profile); } catch {}
    loadRecommendation(profile);
  };

  const handleChangeProfile = () => {
    setShowProfiler(true);
  };

  const handleRefresh = () => {
    if (riskProfile) loadRecommendation(riskProfile);
  };

  // Show profiler modal if no risk profile set
  if (showProfiler) {
    return (
      <div className="space-y-5 p-4 lg:p-6">
        <div className="flex items-center gap-3">
          <PieChart size={20} className="text-primary-fixed" />
          <h1 className="font-headline text-xl font-bold text-on-surface">Portfolio Intelligence</h1>
        </div>
        <GhostBorderCard>
          <div className="text-center py-8 space-y-4">
            <h2 className="text-lg font-headline font-bold text-on-surface">
              What's your risk appetite?
            </h2>
            <p className="text-sm text-on-surface-variant max-w-md mx-auto">
              We need to understand your risk tolerance before building your personalized portfolio.
              This takes less than 30 seconds.
            </p>
          </div>
        </GhostBorderCard>
        <RiskProfilerModal onComplete={handleProfileComplete} />
      </div>
    );
  }

  const meta = riskProfile ? PROFILE_META[riskProfile] : null;
  const ProfileIcon = meta?.icon ?? PieChart;

  return (
    <div className="space-y-5 p-4 lg:p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <PieChart size={20} className="text-primary-fixed" />
          <h1 className="font-headline text-xl font-bold text-on-surface">Portfolio Intelligence</h1>
        </div>
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono text-on-surface-variant hover:text-primary transition-colors disabled:opacity-50"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Risk Profile Card */}
      {riskProfile && meta && (
        <div className={`flex items-center justify-between rounded-lg ${meta.bgColor} border border-outline-variant/30 p-3`}>
          <div className="flex items-center gap-3">
            <ProfileIcon size={18} className={meta.color} />
            <div>
              <span className={`text-xs font-mono font-bold uppercase tracking-wider ${meta.color}`}>
                {meta.label} Profile
              </span>
              <p className="text-[10px] text-on-surface-variant">{meta.desc}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {recommendation?.avg_irs_pct != null && (
              <span className="text-xs font-mono font-bold text-primary-fixed">
                Avg IRS: {recommendation.avg_irs_pct.toFixed(0)}%
              </span>
            )}
            <button
              onClick={handleChangeProfile}
              className="text-[10px] font-mono text-on-surface-variant hover:text-primary underline"
            >
              Change
            </button>
          </div>
        </div>
      )}

      {/* Market Toggle */}
      <div className="flex items-center gap-2">
        {(["IN", "US"] as const).map((m) => (
          <button
            key={m}
            onClick={() => { setMarket(m); if (riskProfile) loadRecommendation(riskProfile); }}
            className={`px-3 py-1.5 text-xs font-mono uppercase tracking-wider transition-colors ${
              market === m
                ? "bg-primary-fixed/10 text-primary-fixed border border-primary-fixed/30"
                : "text-on-surface-variant border border-outline-variant/30 hover:text-primary"
            }`}
          >
            {m === "IN" ? "🇮🇳 India" : "🇺🇸 US"}
          </button>
        ))}
      </div>

      {/* Loading */}
      {loading && (
        <GhostBorderCard>
          <div className="flex items-center justify-center py-12 gap-2">
            <Loader2 size={20} className="animate-spin text-primary" />
            <span className="text-sm text-on-surface-variant">Building your portfolio…</span>
          </div>
        </GhostBorderCard>
      )}

      {/* Error */}
      {error && (
        <GhostBorderCard>
          <div className="text-center py-8 space-y-3">
            <AlertTriangle size={24} className="mx-auto text-error" />
            <p className="text-sm text-error">{error}</p>
            <button onClick={handleRefresh} className="text-sm text-primary hover:underline">
              Try again
            </button>
          </div>
        </GhostBorderCard>
      )}

      {/* Recommendation */}
      {recommendation && !loading && !error && (
        <>
          {/* Pool sections */}
          {recommendation.pools.map((pool) => (
            <PoolSection
              key={pool.name}
              name={pool.name}
              allocation={pool.allocation_pct}
              stocks={pool.stocks}
            />
          ))}

          {/* Total count */}
          <div className="text-center text-xs text-on-surface-variant">
            {recommendation.total_stocks} stocks recommended · Mining &amp; Metals excluded · IRS% {'>'} 65% for Large-Cap
          </div>

          {/* Sell Signals */}
          <SellSignalsPanel market={market} />

          {/* Geopolitical Scan */}
          <GeopoliticalScanPanel market={market} />

          {/* SEBI Disclaimer */}
          <div className="text-[9px] text-on-surface-variant text-center leading-relaxed">
            {recommendation.sebi_disclaimer || "These recommendations are based on quantitative analysis. QuantAlpha is a research tool, not a SEBI-registered investment advisor. Please consult a qualified financial advisor before investing."}
          </div>
        </>
      )}
    </div>
  );
}
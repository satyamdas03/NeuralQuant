"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { api } from "@/lib/api";
import type { ScreenerResponse } from "@/lib/types";
import { ScreenerTable } from "@/components/ScreenerTable";
import RegimeBadge from "@/components/ui/RegimeBadge";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import ScreenerPresets from "@/components/ui/ScreenerPresets";
import { PRESETS, type ScreenerPreset } from "@/data/screener-presets";
import { ScanSearch, Filter } from "lucide-react";
import { trackApiEvent } from "@/lib/analytics";

export default function ScreenerPage() {
  return (
    <Suspense fallback={<ScreenerSkeleton />}>
      <ScreenerInner />
    </Suspense>
  );
}

function ScreenerSkeleton() {
  return (
    <div className="space-y-2 p-4 lg:p-6">
      {Array.from({ length: 10 }).map((_, i) => (
        <div key={i} className="h-12 bg-surface-container rounded-lg animate-pulse" />
      ))}
    </div>
  );
}

function ScreenerInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const urlMarket = (searchParams.get("market") === "IN" ? "IN" : "US") as "US" | "IN";

  const [data, setData] = useState<ScreenerResponse | null>(null);
  const [market, setMarket] = useState<"US" | "IN">(urlMarket);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activePreset, setActivePreset] = useState<string | null>(null);
  // Anjali filters
  const [showAnjaliFilters, setShowAnjaliFilters] = useState(false);
  const [minAnjaliComposite, setMinAnjaliComposite] = useState<number>(-16);
  const [valueSweetSpotOnly, setValueSweetSpotOnly] = useState(false);
  const [excludeLossMaking, setExcludeLossMaking] = useState(false);

  const load = (m: "US" | "IN") => {
    setLoading(true);
    setError(null);
    api
      .getScreenerPreview(m, 50)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load screener"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMarket(urlMarket);
    load(urlMarket);
  }, [urlMarket]);

  // Track screener filter usage (skip initial mount)
  const filtersChangedRef = useRef(false);
  useEffect(() => {
    if (!filtersChangedRef.current) {
      filtersChangedRef.current = true;
      return;
    }
    if (!data) return;
    const filters = JSON.stringify({
      preset: activePreset,
      min_composite: minAnjaliComposite,
      value_sweet_spot: valueSweetSpotOnly,
      exclude_loss_making: excludeLossMaking,
    });
    trackApiEvent("screener_used", { market, filters }).catch(() => {});
  }, [activePreset, minAnjaliComposite, valueSweetSpotOnly, excludeLossMaking, market, data]);

  const handlePresetSelect = (preset: ScreenerPreset | null) => {
    setActivePreset(preset?.id ?? null);
  };

  const filteredResults = (() => {
    if (!data) return [];
    let results = data.results;

    // Apply preset filters
    if (activePreset) {
      const preset = PRESETS.find((p) => p.id === activePreset);
      if (preset) {
        const f = preset.filters;
        results = results.filter((s) => {
          if (f.min_score && s.score_1_10 < f.min_score) return false;
          if (f.min_momentum && s.sub_scores.momentum * 100 < f.min_momentum) return false;
          if (f.max_momentum && s.sub_scores.momentum * 100 > f.max_momentum) return false;
          if (f.min_quality && s.sub_scores.quality * 100 < f.min_quality) return false;
          if (f.min_low_vol && s.sub_scores.low_vol * 100 < f.min_low_vol) return false;
          return true;
        });
      }
    }

    // Apply Anjali filters
    if (minAnjaliComposite > -16 || valueSweetSpotOnly || excludeLossMaking) {
      results = results.filter((s) => {
        // If no Anjali data and filters are active, exclude
        if (!s.anjali) return false;
        if (s.anjali.composite != null && s.anjali.composite < minAnjaliComposite) return false;
        if (valueSweetSpotOnly && !s.anjali.valuation_sweet_spot) return false;
        if (excludeLossMaking && s.anjali.is_loss_making) return false;
        return true;
      });
    }

    return results;
  })();

  const switchMarket = (m: "US" | "IN") => {
    setMarket(m);
    router.replace(`${pathname}?market=${m}`, { scroll: false });
    load(m);
  };

  const hasAnjali = data?.results.some((s) => s.anjali != null) ?? false;

  return (
    <div className="space-y-5 p-4 lg:p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ScanSearch size={20} className="text-primary-fixed" />
          <div>
            <h1 className="font-headline text-xl font-bold text-on-surface">AI Screener</h1>
            <p className="text-xs text-on-surface-variant">
              Stocks ranked by QuantAlpha ForeCast Score™
            </p>
          </div>
        </div>
        {data && <RegimeBadge regime={data.regime_label} />}
      </div>

      <div className="flex items-center gap-2">
        <div className="flex gap-2">
          {(["US", "IN"] as const).map((m) => (
            <button
              key={m}
              onClick={() => switchMarket(m)}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                market === m
                  ? "gradient-cta text-on-primary-container gradient-cta-shadow"
                  : "bg-surface-high text-on-surface-variant hover:bg-surface-highest hover:text-on-surface"
              }`}
            >
              {m === "US" ? "🇺🇸 US Stocks" : "🇮🇳 India (NSE)"}
            </button>
          ))}
        </div>
        {hasAnjali && (
          <button
            onClick={() => setShowAnjaliFilters(!showAnjaliFilters)}
            className={`ml-auto flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-colors rounded ${
              showAnjaliFilters || minAnjaliComposite > -16 || valueSweetSpotOnly || excludeLossMaking
                ? "bg-primary/20 text-primary border border-primary/30"
                : "bg-surface-high text-on-surface-variant hover:bg-surface-highest"
            }`}
          >
            <Filter size={12} />
            QuantFactor
          </button>
        )}
      </div>

      {showAnjaliFilters && hasAnjali && (
        <div className="glass border border-border-glow p-4 space-y-3">
          <div className="flex items-center gap-2 text-xs font-mono text-primary">
            <Filter size={14} />
            QuantFactor Screener Filters
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-on-surface-variant mb-1">
                Min QF Composite
              </label>
              <input
                type="range"
                min={-16}
                max={16}
                step={1}
                value={minAnjaliComposite}
                onChange={(e) => setMinAnjaliComposite(Number(e.target.value))}
                className="w-full accent-primary"
              />
              <div className="text-xs text-on-surface-variant mt-1 font-mono">
                {minAnjaliComposite >= 0 ? `+${minAnjaliComposite}` : minAnjaliComposite} / 16
              </div>
            </div>
            <div className="flex flex-col justify-end">
              <label className="flex items-center gap-2 text-sm text-on-surface cursor-pointer">
                <input
                  type="checkbox"
                  checked={valueSweetSpotOnly}
                  onChange={(e) => setValueSweetSpotOnly(e.target.checked)}
                  className="accent-primary w-4 h-4"
                />
                <span>Value Sweet Spot Only</span>
              </label>
              <span className="text-[10px] text-on-surface-variant ml-6">
                Q2 valuation (best value plays)
              </span>
            </div>
            <div className="flex flex-col justify-end">
              <label className="flex items-center gap-2 text-sm text-on-surface cursor-pointer">
                <input
                  type="checkbox"
                  checked={excludeLossMaking}
                  onChange={(e) => setExcludeLossMaking(e.target.checked)}
                  className="accent-primary w-4 h-4"
                />
                <span>Exclude Loss-Making</span>
              </label>
              <span className="text-[10px] text-on-surface-variant ml-6">
                Hide companies with net losses
              </span>
            </div>
          </div>
        </div>
      )}

      <ScreenerPresets active={activePreset} onSelect={handlePresetSelect} />

      {activePreset && (() => {
        const preset = PRESETS.find(p => p.id === activePreset);
        if (!preset) return null;
        return (
          <div className="bg-primary/10 border border-primary/20 px-4 py-2.5 text-xs text-on-surface leading-relaxed">
            <span className="font-semibold text-primary">{preset.name}:</span> {preset.description}
          </div>
        );
      })()}

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="h-12 bg-surface-container rounded-lg animate-pulse" />
          ))}
        </div>
      ) : error ? (
        <GhostBorderCard>
          <div className="text-center py-8">
            <p className="text-sm text-error">{error}</p>
            <button onClick={() => load(market)} className="mt-3 text-xs text-primary hover:underline">Retry</button>
          </div>
        </GhostBorderCard>
      ) : data ? (
        <ScreenerTable stocks={filteredResults} />
      ) : null}
    </div>
  );
}
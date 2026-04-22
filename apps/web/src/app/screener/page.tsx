"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { api } from "@/lib/api";
import type { ScreenerResponse } from "@/lib/types";
import { ScreenerTable } from "@/components/ScreenerTable";
import RegimeBadge from "@/components/ui/RegimeBadge";
import GlassPanel from "@/components/ui/GlassPanel";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import { ScanSearch } from "lucide-react";

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

  const load = (m: "US" | "IN") => {
    setLoading(true);
    api
      .runScreener({ market: m, max_results: 30 })
      .then(setData)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    setMarket(urlMarket);
    load(urlMarket);
  }, [urlMarket]);

  const switchMarket = (m: "US" | "IN") => {
    setMarket(m);
    router.replace(`${pathname}?market=${m}`, { scroll: false });
    load(m);
  };

  return (
    <div className="space-y-5 p-4 lg:p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ScanSearch size={20} className="text-secondary" />
          <div>
            <h1 className="font-headline text-xl font-bold text-on-surface">AI Screener</h1>
            <p className="text-xs text-on-surface-variant">
              Stocks ranked by NeuralQuant composite AI score
            </p>
          </div>
        </div>
        {data && <RegimeBadge regime={data.regime_label} />}
      </div>

      <div className="flex gap-2">
        {(["US", "IN"] as const).map((m) => (
          <button
            key={m}
            onClick={() => switchMarket(m)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              market === m
                ? "gradient-cta text-on-primary-container gradient-cta-shadow"
                : "bg-surface-high text-on-surface-variant hover:bg-surface-highest hover:text-on-surface"
            }`}
          >
            {m === "US" ? "🇺🇸 US Stocks" : "🇮🇳 India (NSE)"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="h-12 bg-surface-container rounded-lg animate-pulse" />
          ))}
        </div>
      ) : data ? (
        <ScreenerTable stocks={data.results} />
      ) : null}
    </div>
  );
}
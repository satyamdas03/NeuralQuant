"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { api } from "@/lib/api";
import type { ScreenerResponse } from "@/lib/types";
import { ScreenerTable } from "@/components/ScreenerTable";
import { RegimeBadge } from "@/components/RegimeBadge";

export default function ScreenerPage() {
  return (
    <Suspense fallback={<ScreenerSkeleton />}>
      <ScreenerInner />
    </Suspense>
  );
}

function ScreenerSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 10 }).map((_, i) => (
        <div key={i} className="h-12 bg-gray-900 rounded-lg animate-pulse" />
      ))}
    </div>
  );
}

function ScreenerInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  // Respect ?market=IN (or =US) from URL on initial load + on any query change
  const urlMarket = (searchParams.get("market") === "IN" ? "IN" : "US") as "US" | "IN";

  const [data, setData] = useState<ScreenerResponse | null>(null);
  const [market, setMarket] = useState<"US" | "IN">(urlMarket);
  const [loading, setLoading] = useState(true);

  const load = (m: "US" | "IN") => {
    setLoading(true);
    api.runScreener({ market: m, max_results: 30 })
      .then(setData)
      .finally(() => setLoading(false));
  };

  // Keep state in sync if URL changes (e.g. deep-link or back/forward)
  useEffect(() => {
    setMarket(urlMarket);
    load(urlMarket);
  }, [urlMarket]);

  const switchMarket = (m: "US" | "IN") => {
    setMarket(m);
    // Update URL so the choice is shareable / refresh-safe
    router.replace(`${pathname}?market=${m}`, { scroll: false });
    load(m);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">AI Screener</h1>
          <p className="text-gray-400 mt-1">Stocks ranked by NeuralQuant composite AI score</p>
        </div>
        {data && <RegimeBadge label={data.regime_label} />}
      </div>

      <div className="flex gap-2">
        {(["US", "IN"] as const).map((m) => (
          <button
            key={m}
            onClick={() => switchMarket(m)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              market === m ? "bg-violet-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            {m === "US" ? "🇺🇸 US Stocks" : "🇮🇳 India (NSE)"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="h-12 bg-gray-900 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : data ? (
        <ScreenerTable stocks={data.results} />
      ) : null}
    </div>
  );
}

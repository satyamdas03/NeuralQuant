"use client";

import { useState } from "react";
import { authedApi } from "@/lib/api";

type StockOption = {
  ticker: string;  // canonical (no .NS suffix)
  name: string;
  market: "US" | "IN";
};

const POPULAR_STOCKS: StockOption[] = [
  { ticker: "RELIANCE",   name: "Reliance",      market: "IN" },
  { ticker: "TCS",        name: "TCS",           market: "IN" },
  { ticker: "HDFCBANK",   name: "HDFC Bank",     market: "IN" },
  { ticker: "INFY",       name: "Infosys",       market: "IN" },
  { ticker: "AAPL",       name: "Apple",         market: "US" },
  { ticker: "MSFT",       name: "Microsoft",     market: "US" },
  { ticker: "GOOGL",      name: "Alphabet",      market: "US" },
  { ticker: "NVDA",       name: "Nvidia",        market: "US" },
  { ticker: "ICICIBANK",  name: "ICICI Bank",    market: "IN" },
  { ticker: "BHARTIARTL", name: "Bharti Airtel", market: "IN" },
];

interface WelcomeModalProps {
  onClose: () => void;
}

export default function WelcomeModal({ onClose }: WelcomeModalProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggle = (ticker: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(ticker)) {
        next.delete(ticker);
      } else if (next.size < 5) {
        next.add(ticker);
      }
      return next;
    });
  };

  const handleContinue = async () => {
    if (selected.size === 0) {
      onClose();
      return;
    }

    setCreating(true);
    setError(null);
    try {
      // De-duplicate against existing watchlist so re-opened onboarding
      // doesn't fail with 409 for already-saved tickers.
      let existing: Array<{ ticker: string; market: "US" | "IN" }> = [];
      try {
        const list = await authedApi.listWatchlist();
        existing = list.items.map((i) => ({ ticker: i.ticker, market: i.market }));
      } catch {
        // If listing fails (e.g. first-ever login race), proceed with adds anyway.
      }

      const isDup = (t: string, m: "US" | "IN") =>
        existing.some((e) => e.ticker === t && e.market === m);

      const picks = POPULAR_STOCKS.filter((s) => selected.has(s.ticker));
      // Serial inserts: backend enforces a unique (user_id,ticker,market) index;
      // concurrent inserts would race. Serial is plenty fast for ≤5 items.
      for (const s of picks) {
        if (isDup(s.ticker, s.market)) continue;
        try {
          await authedApi.addWatchlist({ ticker: s.ticker, market: s.market });
        } catch (err: unknown) {
          // 409 (already exists) is benign; surface anything else.
          const msg = err instanceof Error ? err.message : String(err);
          if (!msg.includes("409")) {
            console.error("watchlist add failed", s.ticker, msg);
            setError(`Couldn't add ${s.ticker}. Some stocks were saved.`);
          }
        }
      }
    } catch (err) {
      console.error("Failed to create watchlist:", err);
      setError("Couldn't save your watchlist. Please try again.");
    } finally {
      setCreating(false);
      if (!error) onClose();
    }
  };

  const buttonLabel =
    selected.size === 0
      ? "Continue"
      : `Add ${selected.size} stock${selected.size > 1 ? "s" : ""}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="glass-strong ghost-border mx-4 w-full max-w-md rounded-2xl p-8">
        <h2 className="font-headline text-xl font-bold text-on-surface">
          Welcome to NeuralQuant
        </h2>
        <p className="mt-2 text-sm text-on-surface-variant">
          Pick 3–5 stocks to start your first watchlist. You can always change
          these later.
        </p>

        <div className="mt-6 grid grid-cols-2 gap-3">
          {POPULAR_STOCKS.map((stock) => {
            const isSelected = selected.has(stock.ticker);
            return (
              <button
                key={stock.ticker}
                onClick={() => toggle(stock.ticker)}
                className={`rounded-lg border px-3 py-2.5 text-left text-sm font-medium transition-colors ${
                  isSelected
                    ? "bg-primary/20 text-primary ghost-border"
                    : "bg-surface-low text-on-surface-variant border-ghost-border hover:bg-surface-high"
                }`}
              >
                <span className="block text-sm">{stock.name}</span>
                <span className="block text-xs opacity-60">
                  {stock.ticker}{stock.market === "IN" ? " · NSE" : ""}
                </span>
              </button>
            );
          })}
        </div>

        {error && (
          <p className="mt-4 text-xs text-error">{error}</p>
        )}

        <div className="mt-6 flex items-center justify-between">
          <button
            onClick={onClose}
            className="text-sm text-on-surface-variant transition-colors hover:text-on-surface"
          >
            Skip
          </button>
          <button
            onClick={handleContinue}
            disabled={creating}
            className="rounded-lg bg-gradient-to-r from-[#c1c1ff] to-[#bdf4ff] px-5 py-2.5 text-sm font-semibold text-[#0f0f1a] transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {creating ? "Creating..." : buttonLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase/client";

const POPULAR_STOCKS = [
  { ticker: "RELIANCE.NS", name: "Reliance" },
  { ticker: "TCS.NS", name: "TCS" },
  { ticker: "HDFCBANK.NS", name: "HDFC Bank" },
  { ticker: "INFY.NS", name: "Infosys" },
  { ticker: "AAPL", name: "Apple" },
  { ticker: "MSFT", name: "Microsoft" },
  { ticker: "GOOGL", name: "Alphabet" },
  { ticker: "NVDA", name: "Nvidia" },
  { ticker: "ICICIBANK.NS", name: "ICICI Bank" },
  { ticker: "BHARTIARTL.NS", name: "Bharti Airtel" },
];

interface WelcomeModalProps {
  onClose: () => void;
}

export default function WelcomeModal({ onClose }: WelcomeModalProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [creating, setCreating] = useState(false);

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
    try {
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();

      if (user) {
        const { error } = await supabase.from("watchlists").insert({
          name: "My Watchlist",
          user_id: user.id,
          tickers: Array.from(selected),
        });

        if (error) {
          console.error("Failed to create watchlist:", error);
        }
      }
    } catch (err) {
      console.error("Failed to create watchlist:", err);
    } finally {
      setCreating(false);
      onClose();
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
                <span className="block text-xs opacity-60">{stock.ticker}</span>
              </button>
            );
          })}
        </div>

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
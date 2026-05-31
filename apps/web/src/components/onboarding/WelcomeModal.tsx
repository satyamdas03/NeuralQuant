"use client";

import { useState } from "react";
import { authedApi } from "@/lib/api";
import { useWalkthrough } from "./WalkthroughProvider";
import { Share2, ChevronRight, ChevronLeft, Sparkles } from "lucide-react";

type StockOption = {
  ticker: string;  // canonical (no .NS suffix)
  name: string;
  market: "US" | "IN";
};

const POPULAR_STOCKS: StockOption[] = [
  { ticker: "RELIANCE",   name: "Reliance",      market: "IN" },
  { ticker: "TCS",        name: "TCS",           market: "IN" },
  { ticker: "HDFCBANK",   name: "HDFC Bank",     market: "IN" },
  { ticker: "INFY",       name: "Infosys",        market: "IN" },
  { ticker: "AAPL",       name: "Apple",          market: "US" },
  { ticker: "MSFT",       name: "Microsoft",      market: "US" },
  { ticker: "GOOGL",      name: "Alphabet",       market: "US" },
  { ticker: "NVDA",       name: "Nvidia",         market: "US" },
  { ticker: "ICICIBANK",  name: "ICICI Bank",     market: "IN" },
  { ticker: "BHARTIARTL", name: "Bharti Airtel",  market: "IN" },
];

interface WelcomeModalProps {
  onClose: () => void;
}

export default function WelcomeModal({ onClose }: WelcomeModalProps) {
  const { startTour } = useWalkthrough();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClose = () => {
    onClose();
    setTimeout(() => startTour(), 800);
  };

  const toggle = (ticker: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(ticker)) next.delete(ticker);
      else if (next.size < 5) next.add(ticker);
      return next;
    });
  };

  const handleContinue = async () => {
    if (selected.size === 0) {
      setStep(2);
      return;
    }

    setCreating(true);
    setError(null);
    try {
      let existing: Array<{ ticker: string; market: "US" | "IN" }> = [];
      try {
        const list = await authedApi.listWatchlist();
        existing = list.items.map((i) => ({ ticker: i.ticker, market: i.market }));
      } catch { /* proceed anyway */ }

      const isDup = (t: string, m: "US" | "IN") =>
        existing.some((e) => e.ticker === t && e.market === m);

      const picks = POPULAR_STOCKS.filter((s) => selected.has(s.ticker));
      for (const s of picks) {
        if (isDup(s.ticker, s.market)) continue;
        try {
          await authedApi.addWatchlist({ ticker: s.ticker, market: s.market });
        } catch (err: unknown) {
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
      if (!error) setStep(2);
    }
  };

  const buttonLabel =
    selected.size === 0 ? "Continue" : `Add ${selected.size} stock${selected.size > 1 ? "s" : ""}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="glass-strong ghost-border mx-4 w-full max-w-md p-8">
        {/* Step indicator */}
        <div className="flex items-center justify-center gap-2 mb-6">
          {[1, 2, 3].map((s) => (
            <div
              key={s}
              className={`h-2 w-2 rounded-full transition-colors ${
                s === step ? "bg-accent" : s < step ? "bg-accent/50" : "bg-ghost-border"
              }`}
            />
          ))}
        </div>

        {/* Step 1: Stock Picker */}
        {step === 1 && (
          <>
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
                    className={`border px-3 py-2.5 text-left text-sm font-medium transition-colors ${
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

            {error && <p className="mt-4 text-xs text-error">{error}</p>}

            <div className="mt-6 flex items-center justify-between">
              <button
                onClick={handleClose}
                className="text-sm text-on-surface-variant transition-colors hover:text-on-surface"
              >
                Skip
              </button>
              <button
                onClick={handleContinue}
                disabled={creating}
                className="bg-gradient-to-r from-[#c1c1ff] to-[#bdf4ff] px-5 py-2.5 text-sm font-semibold text-[#0f0f1a] transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {creating ? "Creating..." : buttonLabel}
              </button>
            </div>
          </>
        )}

        {/* Step 2: Share Feature Intro */}
        {step === 2 && (
          <>
            <div className="flex flex-col items-center text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-accent/10">
                <Share2 className="h-8 w-8 text-accent" />
              </div>
              <h2 className="font-headline text-xl font-bold text-on-surface">
                Share Your Analysis
              </h2>
              <p className="mt-2 text-sm text-on-surface-variant">
                After running a PARA-DEBATE analysis, tap &quot;Share Analysis&quot; to
                create a public link. Anyone can view it — no login required.
              </p>
              <p className="mt-3 text-sm text-on-surface-variant">
                Perfect for Twitter, WhatsApp, or your investment group.
              </p>
            </div>

            <div className="mt-6 flex items-center justify-between">
              <button
                onClick={() => setStep(1)}
                className="flex items-center gap-1 text-sm text-on-surface-variant transition-colors hover:text-on-surface"
              >
                <ChevronLeft className="h-4 w-4" /> Back
              </button>
              <button
                onClick={() => setStep(3)}
                className="flex items-center gap-1 bg-gradient-to-r from-[#c1c1ff] to-[#bdf4ff] px-5 py-2.5 text-sm font-semibold text-[#0f0f1a] transition-opacity hover:opacity-90"
              >
                Next <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </>
        )}

        {/* Step 3: You're All Set */}
        {step === 3 && (
          <>
            <div className="flex flex-col items-center text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-accent/10">
                <Sparkles className="h-8 w-8 text-accent" />
              </div>
              <h2 className="font-headline text-xl font-bold text-on-surface">
                You&apos;re All Set
              </h2>
              <p className="mt-2 text-sm text-on-surface-variant">
                Start exploring NeuralQuant. Run your first AI analysis, build a
                watchlist, or try the screener.
              </p>
              <p className="mt-3 text-xs text-on-surface-variant">
                The interactive tour will guide you through the key features.
              </p>
            </div>

            <div className="mt-6 flex items-center justify-between">
              <button
                onClick={() => setStep(2)}
                className="flex items-center gap-1 text-sm text-on-surface-variant transition-colors hover:text-on-surface"
              >
                <ChevronLeft className="h-4 w-4" /> Back
              </button>
              <button
                onClick={handleClose}
                className="bg-gradient-to-r from-[#c1c1ff] to-[#bdf4ff] px-5 py-2.5 text-sm font-semibold text-[#0f0f1a] transition-opacity hover:opacity-90"
              >
                Start Exploring
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
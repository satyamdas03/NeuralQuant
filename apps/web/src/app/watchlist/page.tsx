"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { authedApi } from "@/lib/api";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import GradientButton from "@/components/ui/GradientButton";
import { Star, Trash2 } from "lucide-react";

type Item = { id: string; ticker: string; market: "US" | "IN"; note: string | null; created_at: string };

export default function WatchlistPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [newTicker, setNewTicker] = useState("");
  const [newMarket, setNewMarket] = useState<"US" | "IN">("US");
  const [adding, setAdding] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const r = await authedApi.listWatchlist();
      setItems(r.items);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!newTicker.trim()) return;
    setAdding(true);
    try {
      await authedApi.addWatchlist({ ticker: newTicker.trim().toUpperCase(), market: newMarket });
      setNewTicker("");
      refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await authedApi.deleteWatchlist(id);
      setItems((cur) => cur.filter((x) => x.id !== id));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5 p-4 lg:p-6">
      <div className="flex items-center gap-3">
        <Star size={20} className="text-primary" />
        <div>
          <h1 className="font-headline text-xl font-bold text-on-surface">Your Watchlist</h1>
          <p className="text-xs text-on-surface-variant">
            Track your favourite stocks across US and India
          </p>
        </div>
      </div>

      <GhostBorderCard>
        <form onSubmit={handleAdd} className="flex gap-2">
          <input
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value)}
            placeholder="AAPL or RELIANCE"
            className="flex-1 rounded-lg bg-surface-high px-3 py-2 text-sm uppercase text-on-surface outline-none placeholder:text-on-surface-variant focus:ring-1 focus:ring-primary"
          />
          <select
            value={newMarket}
            onChange={(e) => setNewMarket(e.target.value as "US" | "IN")}
            className="rounded-lg bg-surface-high px-3 py-2 text-sm text-on-surface outline-none"
          >
            <option value="US">US</option>
            <option value="IN">IN</option>
          </select>
          <GradientButton type="submit" size="sm" disabled={adding}>
            {adding ? "Adding…" : "Add"}
          </GradientButton>
        </form>
      </GhostBorderCard>

      {error && <p className="text-sm text-error">{error}</p>}

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-14 bg-surface-container rounded-xl animate-pulse" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <p className="text-sm text-on-surface-variant">
          No tickers yet. Add a stock above, or browse the{" "}
          <Link href="/screener" className="text-secondary hover:text-primary">
            screener
          </Link>
          .
        </p>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <GhostBorderCard key={item.id} hover>
              <div className="flex items-center justify-between">
                <div>
                  <Link
                    href={`/stocks/${item.ticker}?market=${item.market}`}
                    className="font-semibold text-on-surface hover:text-primary transition-colors"
                  >
                    {item.ticker}
                  </Link>
                  <span className="ml-2 text-xs text-on-surface-variant">{item.market}</span>
                  {item.note && (
                    <p className="mt-1 text-xs text-on-surface-variant">{item.note}</p>
                  )}
                </div>
                <button
                  onClick={() => handleDelete(item.id)}
                  className="rounded-lg p-2 text-on-surface-variant hover:bg-surface-high hover:text-error transition-colors"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </GhostBorderCard>
          ))}
        </div>
      )}
    </div>
  );
}
"use client";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { authedApi } from "@/lib/api";

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
    <div className="min-h-screen px-6 py-10 max-w-3xl mx-auto">
      <header className="mb-8 flex items-center justify-between">
        <h1 className="text-3xl font-semibold">Your watchlist</h1>
        <form action="/auth/sign-out" method="POST">
          <button className="text-sm text-white/60 hover:text-white">Sign out</button>
        </form>
      </header>

      <form onSubmit={handleAdd} className="mb-8 flex gap-2">
        <input
          value={newTicker}
          onChange={(e) => setNewTicker(e.target.value)}
          placeholder="AAPL or RELIANCE"
          className="flex-1 rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm uppercase"
        />
        <select
          value={newMarket}
          onChange={(e) => setNewMarket(e.target.value as "US" | "IN")}
          className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm"
        >
          <option value="US">US</option>
          <option value="IN">IN</option>
        </select>
        <button
          type="submit"
          disabled={adding}
          className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-medium text-black hover:bg-emerald-400 disabled:opacity-50"
        >
          {adding ? "Adding..." : "Add"}
        </button>
      </form>

      {error && <p className="mb-4 text-sm text-red-400">{error}</p>}
      {loading ? (
        <p className="text-white/60">Loading...</p>
      ) : items.length === 0 ? (
        <p className="text-white/60">
          No tickers yet. Add a stock above, or browse the{" "}
          <Link href="/screener" className="text-emerald-400 hover:underline">
            screener
          </Link>
          .
        </p>
      ) : (
        <ul className="space-y-2">
          {items.map((item) => (
            <li
              key={item.id}
              className="flex items-center justify-between rounded-lg border border-white/10 bg-white/5 px-4 py-3"
            >
              <div>
                <Link
                  href={`/stocks/${item.ticker}?market=${item.market}`}
                  className="font-medium text-white hover:text-emerald-400"
                >
                  {item.ticker}
                </Link>
                <span className="ml-2 text-xs text-white/50">{item.market}</span>
                {item.note && <p className="mt-1 text-xs text-white/60">{item.note}</p>}
              </div>
              <button
                onClick={() => handleDelete(item.id)}
                className="text-sm text-red-400 hover:text-red-300"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

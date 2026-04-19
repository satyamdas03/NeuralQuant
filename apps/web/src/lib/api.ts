import type {
  AIScore, Market, ScreenerRequest, ScreenerResponse,
  AnalystRequest, AnalystResponse,
  QueryRequest, QueryResponse,
  MarketOverview, MarketNews, MarketSectors,
  MarketMovers, StockChart, StockMeta,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API error ${response.status}: ${error}`);
  }
  return response.json();
}

// Authed variant — attaches Supabase access token for /auth/* and /watchlist/*
async function authedFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const { createClient } = await import("./supabase/client");
  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const headers = new Headers(options?.headers || {});
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (response.status === 401 && typeof window !== "undefined") {
    const nextUrl = window.location.pathname + window.location.search;
    window.location.href = `/login?next=${encodeURIComponent(nextUrl)}`;
    throw new Error("auth required — redirecting to login");
  }
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API ${response.status}: ${error}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export const authedApi = {
  me: () => authedFetch<{ id: string; email: string; tier: string; limits: Record<string, number> }>("/auth/me"),
  listWatchlist: () =>
    authedFetch<{ items: Array<{ id: string; ticker: string; market: "US" | "IN"; note: string | null; created_at: string }>; count: number }>(
      "/watchlist"
    ),
  addWatchlist: (body: { ticker: string; market: "US" | "IN"; note?: string }) =>
    authedFetch<{ id: string; ticker: string; market: "US" | "IN"; note: string | null; created_at: string }>("/watchlist", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteWatchlist: (id: string) =>
    authedFetch<void>(`/watchlist/${id}`, { method: "DELETE" }),
};

export const api = {
  getStock: (ticker: string, market: Market = "US") =>
    apiFetch<AIScore>(`/stocks/${ticker}?market=${market}`),

  runScreener: (body: ScreenerRequest) =>
    authedFetch<ScreenerResponse>("/screener", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // Public cache-only top-N; no auth, no quota (dashboard preview).
  getScreenerPreview: (market: Market = "US", n = 8) =>
    apiFetch<ScreenerResponse>(`/screener/preview?market=${market}&n=${n}`),

  runAnalyst: (body: AnalystRequest) =>
    authedFetch<AnalystResponse>("/analyst", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  runQuery: (body: QueryRequest) =>
    authedFetch<QueryResponse>("/query", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getMarketOverview: () => apiFetch<MarketOverview>("/market/overview"),
  getMarketNews: (n = 8) => apiFetch<MarketNews>(`/market/news?n=${n}`),
  getMarketSectors: () => apiFetch<MarketSectors>("/market/sectors"),
  getMarketMovers: () => apiFetch<MarketMovers>("/market/movers"),
  getStockChart: (ticker: string, period = "1mo", market: Market = "US") =>
    apiFetch<StockChart>(`/stocks/${ticker}/chart?period=${period}&market=${market}`),
  getStockMeta: (ticker: string, market: Market = "US") =>
    apiFetch<StockMeta>(`/stocks/${ticker}/meta?market=${market}`),
};

import type {
  AIScore, Market, ScreenerRequest, ScreenerResponse,
  AnalystRequest, AnalystResponse,
  QueryRequest, QueryResponse, StructuredQueryResponse,
  MarketOverview, MarketNews, MarketSectors,
  MarketMovers, StockChart, StockMeta,
  SentimentResponse, BacktestRequest, BacktestResponse,
  AlertSubscription, AlertDelivery, NewsDeskResponse,
} from "./types";

// Route all requests through Next.js /api/ rewrite proxy to avoid CORS issues.
// next.config.ts rewrites /api/:path* → NEXT_PUBLIC_API_URL/:path*
const API_BASE = "/api";

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
async function authedFetch<T>(path: string, options?: RequestInit & { signal?: AbortSignal }): Promise<T> {
  const { createClient } = await import("./supabase/client");
  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const headers = new Headers(options?.headers || {});
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers, signal: options?.signal });
  if (response.status === 401) {
    throw new Error("auth required");
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

  // Alerts
  listAlertSubscriptions: () =>
    authedFetch<{ items: AlertSubscription[]; count: number }>("/alerts/subscriptions"),
  createAlertSubscription: (body: {
    ticker: string; market?: "US" | "IN"; alert_type?: "score_change" | "regime_change" | "threshold";
    threshold?: number; min_delta?: number;
  }) =>
    authedFetch<AlertSubscription>("/alerts/subscriptions", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteAlertSubscription: (id: string) =>
    authedFetch<void>(`/alerts/subscriptions/${id}`, { method: "DELETE" }),
  listAlertDeliveries: (limit = 20) =>
    authedFetch<{ items: AlertDelivery[]; count: number }>(`/alerts/deliveries?limit=${limit}`),

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

  /**
   * SSE-based analyst: streams keep-alive pings every 8 s from the backend
   * so Render's idle-connection timeout never fires during the debate.
   * Resolves with the full AnalystResponse when the debate is complete.
   * Client-side AbortController caps total wait at 100 s.
   */
  runAnalystStream: async (body: AnalystRequest): Promise<AnalystResponse> => {
    const { createClient } = await import("./supabase/client");
    const supabase = createClient();
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    // SSE CANNOT go through the Next.js /api rewrite proxy — Vercel's
    // serverless function timeout (10–30 s) drops long-lived streams.
    // Hit Render directly instead.
    const sseBase = process.env.NEXT_PUBLIC_API_URL || "https://neuralquant.onrender.com";
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 130_000); // 130s hard cap (90s debate + 30s context + buffer)
    try {
      const response = await fetch(`${sseBase}/analyst/stream`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!response.ok) {
        const err = await response.text();
        throw new Error(`API ${response.status}: ${err}`);
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";           // keep incomplete last line
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6).trim();
          if (payload === "[DONE]") return Promise.reject(new Error("Stream closed without result"));
          try {
            const evt = JSON.parse(payload);
            if (evt.status === "done") return evt.result as AnalystResponse;
            if (evt.status === "error") throw new Error(evt.message ?? "PARA-DEBATE failed");
            // status === "running": ignore keep-alive ticks
          } catch (e) {
            if (e instanceof SyntaxError) continue; // malformed line, skip
            throw e;
          }
        }
      }
      throw new Error("SSE stream ended without result");
    } finally {
      clearTimeout(timeout);
    }
  },

  runQuery: (body: QueryRequest, signal?: AbortSignal) =>
    authedFetch<StructuredQueryResponse>("/query/v2", {
      method: "POST",
      body: JSON.stringify(body),
      signal,
    }),

  /**
   * SSE-based query: streams phase labels ("Scanning market headlines...",
   * "Running AI analysis...") so the user sees what the AI is doing.
   * Falls back to runQuery() on SSE failure.
   */
  runQueryStream: async (
    body: QueryRequest,
    signal: AbortSignal,
    onPhase: (phase: string, label: string) => void,
  ): Promise<StructuredQueryResponse> => {
    const { createClient } = await import("./supabase/client");
    const supabase = createClient();
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    // SSE must bypass Next.js proxy (Vercel serverless timeout kills streams)
    const sseBase = process.env.NEXT_PUBLIC_API_URL || "https://neuralquant.onrender.com";

    try {
      const response = await fetch(`${sseBase}/query/v2/stream`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
        signal,
      });

      if (!response.ok) {
        const err = await response.text();
        throw new Error(`API ${response.status}: ${err}`);
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6).trim();
          if (payload === "[DONE]") throw new Error("Stream closed without result");
          try {
            const evt = JSON.parse(payload);
            if (evt.status === "phase") {
              onPhase(evt.phase, evt.label);
            } else if (evt.status === "done") {
              return evt.result as StructuredQueryResponse;
            } else if (evt.status === "error") {
              throw new Error(evt.message ?? "Query failed");
            }
            // status === "running": keep-alive tick, ignore
          } catch (e) {
            if (e instanceof SyntaxError) continue; // malformed line
            throw e;
          }
        }
      }
      throw new Error("SSE stream ended without result");
    } catch (streamErr) {
      // Fallback: try the regular endpoint if SSE fails
      try {
        return await api.runQuery(body, signal);
      } catch {
        throw streamErr;
      }
    }
  },

  getMarketOverview: () => apiFetch<MarketOverview>("/market/overview"),
  getNewsDesk: () => apiFetch<NewsDeskResponse>("/news"),
  getMarketNews: (n = 8) => apiFetch<MarketNews>(`/market/news?n=${n}`),
  getMarketSectors: () => apiFetch<MarketSectors>("/market/sectors"),
  getMarketMovers: () => apiFetch<MarketMovers>("/market/movers"),
  getStockChart: (ticker: string, period = "1mo", market: Market = "US") =>
    apiFetch<StockChart>(`/stocks/${ticker}/chart?period=${period}&market=${market}`),
  getStockMeta: (ticker: string, market: Market = "US") =>
    apiFetch<StockMeta>(`/stocks/${ticker}/meta?market=${market}`),

  // Pillar C: sentiment (public, free, cached at edge by client)
  getSentiment: (ticker: string, market: Market = "US", limit = 15) =>
    apiFetch<SentimentResponse>(`/sentiment/news/${ticker}?market=${market}&limit=${limit}`),
};

// Authed — counts against backtest_per_day tier cap
export const authedBacktest = {
  run: (body: BacktestRequest) =>
    authedFetch<BacktestResponse>("/backtest", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

// Broker integration — deep-link trade tickets
export const brokerApi = {
  getDeepLink: (symbol: string, side: "buy" | "sell" = "buy", broker: "alpaca" | "zerodha" = "alpaca") =>
    authedFetch<{ url: string; broker: string; symbol: string; side: string; note: string }>("/broker/deep-link", {
      method: "POST",
      body: JSON.stringify({ symbol, side, broker }),
    }),

  getAccount: () =>
    authedFetch<Record<string, string | number | boolean>>("/broker/account"),

  getPositions: () =>
    authedFetch<Record<string, string>[]>("/broker/positions"),
};

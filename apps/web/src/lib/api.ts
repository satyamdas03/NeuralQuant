import type {
  AIScore, ScreenerRequest, ScreenerResponse,
  AnalystRequest, AnalystResponse,
  QueryRequest, QueryResponse,
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

export const api = {
  getStock: (ticker: string, market = "US") =>
    apiFetch<AIScore>(`/stocks/${ticker}?market=${market}`),

  runScreener: (body: ScreenerRequest) =>
    apiFetch<ScreenerResponse>("/screener", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  runAnalyst: (body: AnalystRequest) =>
    apiFetch<AnalystResponse>("/analyst", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  runQuery: (body: QueryRequest) =>
    apiFetch<QueryResponse>("/query", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

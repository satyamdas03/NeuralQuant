/** API client — all calls go to NeuralQuant backend. Mobile is pure client. */

import axios from 'axios';

const API_BASE = process.env.EXPO_PUBLIC_API_URL || 'https://neuralquant.onrender.com';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// Auth token interceptor
api.interceptors.request.use((config) => {
  const token = globalThis.__NQ_AUTH_TOKEN;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Stock endpoints ──────────────────────────────────────────────────
export const fetchStockSnapshot = (ticker: string) =>
  api.get(`/stocks/${ticker}`).then((r) => r.data);

export const fetchStockAnjali = (ticker: string) =>
  api.get(`/stocks/${ticker}/anjali`).then((r) => r.data);

// ── Screener ─────────────────────────────────────────────────────────
export const fetchScreenerResults = (params: Record<string, unknown>) =>
  api.get('/screener', { params }).then((r) => r.data);

// ── Ask Morgan ────────────────────────────────────────────────────────
export const askMorganStream = (question: string, ticker?: string, market?: string) =>
  `${API_BASE}/query/v2/stream?` + new URLSearchParams({
    question,
    ...(ticker ? { ticker } : {}),
    ...(market ? { market } : {}),
  }).toString();

export const askMorgan = (body: Record<string, unknown>) =>
  api.post('/query/v2', body).then((r) => r.data);

// ── Market ───────────────────────────────────────────────────────────
export const fetchMarketMovers = () => api.get('/market/movers').then((r) => r.data);
export const fetchMarketTrending = (limit = 10) =>
  api.get('/market/trending', { params: { limit } }).then((r) => r.data);

// ── Portfolio / Astra ─────────────────────────────────────────────────
export const fetchAstraRecommend = (riskProfile: string) =>
  api.post('/astra/recommend', { risk_profile: riskProfile }).then((r) => r.data);

export const fetchSellSignals = () => api.get('/astra/sell-signals').then((r) => r.data);

export const saveRiskProfile = (profile: string) =>
  api.post('/astra/risk-profile', { risk_profile: profile }).then((r) => r.data);

export const fetchWatchlist = () => api.get('/watchlist').then((r) => r.data);

export const fetchPortfolioAssess = (holdings: any[]) =>
  api.post('/astra/assess', holdings).then((r) => r.data);

// ── Mobile push ──────────────────────────────────────────────────────
export const registerPushToken = (token: string, platform: 'ios' | 'android') =>
  api.post('/mobile/push-token', { token, platform }).then((r) => r.data);

export const removePushToken = () => api.delete('/mobile/push-token').then((r) => r.data);

export default api;
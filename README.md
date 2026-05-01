<div align="center">

# NeuralQuant

**AI-Powered Stock Intelligence Platform — v4.1.0 (Quality Upgrade)**

*Institutional-grade quant research + 7-agent AI debate with live technical indicators, insider sentiment, and sector peer comparison. US & India. 100% live data.*

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black?logo=nextdotjs)](https://nextjs.org)
[![Claude Sonnet 4.6](https://img.shields.io/badge/Claude-Sonnet%204.6-orange?logo=anthropic&logoColor=white)](https://anthropic.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-33%2B%20passing-brightgreen)](apps/api/tests)
[![Data](https://img.shields.io/badge/data-100%25%20live-brightgreen)](#data-sources)

</div>

---

## Phase 4 Complete (v4.1.0)

| Pillar | Scope | Status |
|---|---|---|
| **A1** | Supabase auth, watchlists, tiers (free/investor/pro/api) | ✅ LIVE |
| **A2** | Per-tier rate limiting via `public.usage_log` | ✅ LIVE |
| **B** | 503 US + 200 NSE universe, sector-adjusted factor ranks, nightly `score_cache` | ✅ LIVE |
| **C** | Fitted HMM, ISM PMI, Reddit/StockTwits sentiment | Plan written |
| **D** | Backtesting engine (backtrader) | Plan written |
| **UI** | Obsidian Quantum design system — full visual overhaul | ✅ COMPLETE |
| **IN** | NSE Bhavcopy realtime, delivery_pct signal, India VIX regime heuristics | ✅ COMPLETE |
| **Alerts** | Email alerts (Resend) on score/regime/threshold changes | ✅ COMPLETE |
| **SSE** | Real-time score streaming via EventSource | ✅ COMPLETE |
| **Stripe** | Checkout + billing webhook | Deferred |
| **v4.1** | Finnhub technical indicators, insider sentiment, news sentiment, sector medians, India macro, conversation memory, adversarial enrichment, head analyst weight fix | ✅ LIVE |

**Live deploys:**
- API (Render): `https://neuralquant.onrender.com`
- Web (Vercel): `https://neuralquant.vercel.app`

---

## What is NeuralQuant?

NeuralQuant is a full-stack AI stock intelligence platform that combines a **5-factor quantitative signal engine** with a **7-agent AI analyst debate system** (PARA-DEBATE) to deliver institutional-grade research at retail speed — backed entirely by **live, real data**.

- **Ask in plain English.** *"Is NVDA a buy right now?"* — get a structured answer citing NeuralQuant's own live score (9/10), P/E, price vs. analyst target, and FRED macro conditions.
- **See every reason.** Danelfin-style feature attribution shows the exact factors (Quality, Momentum, Value, Low-Vol, Short Interest / Delivery %) driving each AI score.
- **India + US, day one.** Full 5-factor AI scoring for 200+ NSE stocks alongside 503 NYSE/NASDAQ names. India market uses delivery_pct as a liquidity conviction signal and India VIX-based regime heuristics.
- **7 agents, one verdict.** MACRO, FUNDAMENTAL, TECHNICAL, SENTIMENT, GEOPOLITICAL, and ADVERSARIAL specialists debate in parallel; the HEAD ANALYST synthesises the conviction call.
- **Zero synthetic data.** Every score, every macro figure, every news headline is pulled from live sources — FRED, yfinance, NSE Bhavcopy, SEC EDGAR.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Next.js 16 Frontend (Obsidian Quantum)           │
│  Dashboard · Screener · Stock Detail · Ask AI · Backtest · Alerts   │
│  Space Grotesk + Inter · 4-level surface hierarchy · Glassmorphism  │
└────────────────────────┬────────────────────────────────────────────┘
                         │ REST / JSON / SSE
┌────────────────────────▼────────────────────────────────────────────┐
│                      FastAPI (nq-api v4.0.0)                         │
│  GET  /stocks/{ticker}        GET /stocks/{ticker}/chart             │
│  GET  /stocks/{ticker}/meta   GET /stocks/{ticker}/stream (SSE)     │
│  POST /screener               POST /analyst                          │
│  POST /query (multi-turn)     GET  /market/*                        │
│  GET  /sentiment/{ticker}     POST /backtest                         │
│  /watchlist · /alerts · /auth/me                                     │
└──────────┬──────────────────────┬───────────────────────────────────┘
           │                      │
┌──────────▼──────────┐  ┌────────▼──────────────────────────────────┐
│  nq-signals engine  │  │        PARA-DEBATE Orchestrator             │
│  ─────────────────  │  │  ────────────────────────────────────────  │
│  HMM Regime (4)     │  │  MACRO        ─┐                           │
│  Quality / Momentum │  │  FUNDAMENTAL  ├─ asyncio.gather()          │
│  Value (P/E + P/B)  │  │  TECHNICAL    │   (all 6 in parallel)      │
│  Low-Volatility     │  │  SENTIMENT    │                            │
│  Short Interest (US)│  │  GEOPOLITICAL ├──► HEAD ANALYST            │
│  Delivery % (IN)    │  │  ADVERSARIAL  ┘    (synthesis + verdict)   │
│  Insider (EDGAR F4) │  └────────────────────────────────────────────┘
└──────────┬──────────┘
┌──────────▼──────────┐
│    nq-data layer    │
│  ─────────────────  │
│  yfinance (US/IN)   │   Live prices, OHLCV, fundamentals, news
│  NSE Bhavcopy (IN)  │   EOD data + delivery_pct
│  FRED API (macro)   │   HY Spread, CPI, Fed Funds, 2Y/10Y yields
│  EDGAR Form 4       │   Insider buying/selling signals
│  Finnhub API        │   RSI/MACD/ATR/SMA, insider sentiment, news sentiment
│  DuckDB DataStore   │   Zero-copy columnar cache
└─────────────────────┘
```

---

## Data Sources

Every number shown in NeuralQuant is sourced from live APIs — no synthetic data, no stale snapshots.

| Data Point | Source | Refresh |
|---|---|---|
| VIX / India VIX | yfinance `^VIX` / `^INDIAVIX` | Real-time |
| S&P 500 vs 200-day MA | yfinance `^GSPC` | Real-time |
| SPX 1-month return | yfinance `^GSPC` | Real-time |
| HY Credit Spread OAS | FRED `BAMLH0A0HYM2` | Daily |
| ISM PMI | FRED `MANEMP` | Monthly |
| Gross profit margin | yfinance `grossMargins` | Quarterly |
| Piotroski F-score (0–9) | yfinance financials | Quarterly |
| Accruals ratio | yfinance (NI - OCF) / TA | Quarterly |
| 12-1 month momentum | yfinance 14-month OHLCV | Daily |
| Realized 1Y volatility | yfinance price history | Daily |
| P/E TTM / P/B ratio | yfinance | Real-time |
| Short interest % float (US) | yfinance `shortPercentOfFloat` | Bi-weekly |
| Delivery % (IN) | NSE Bhavcopy | Daily |
| Insider buying/selling | SEC EDGAR Form 4 | As filed |
| Live stock price | yfinance info | Real-time |
| Analyst price target | yfinance `targetMeanPrice` | As published |
| Market news headlines | Yahoo Finance news feed | Real-time |
| RSI-14, MACD, ATR-14, SMA-50/200 | Finnhub candles (1Y daily) | 15 min |
| Volume ratio (today vs 20d avg) | Finnhub candles | 15 min |
| Insider net buy ratio + cluster score | Finnhub insider sentiment API | 1 hour |
| News sentiment (bullish/bearish %, buzz) | Finnhub news sentiment API | 30 min |
| Sector peer medians (P/E, ROE, D/E) | NeuralQuant score_cache | Nightly |

---

## The 5-Factor Model

Scores are computed cross-sectionally within a reference universe — **no hardcoded thresholds**, everything is relative.

**US Market:**

| Factor | Signal | Weight (Risk-On) |
|---|---|---|
| **Quality** | Gross margin + Piotroski F-score + Accruals ratio | 25% |
| **Momentum** | 12-1 month price return (Jegadeesh-Titman) | 25% |
| **Value** | Inverse of (P/E rank x 0.5 + P/B rank x 0.5) | 10% |
| **Low Volatility** | Inverse of realized 1Y vol + beta rank | 15% |
| **Short Interest** | Inverse of short float rank | 10% |
| **Insider** | EDGAR Form 4 cluster score | 5% |

**India Market:**

| Factor | Signal | Weight (Risk-On) |
|---|---|---|
| **Quality** | Gross margin + Piotroski F-score + Accruals ratio | 25% |
| **Momentum** | 12-1 month price return (crash-protected) | 25% |
| **Value** | Inverse of (P/E rank x 0.5 + P/B rank x 0.5) | 10% |
| **Low Volatility** | Inverse of realized 1Y vol + beta rank | 15% |
| **Delivery %** | Institutional conviction via delivery_pct rank | 10% |
| **Insider** | EDGAR Form 4 cluster score | 5% |

Regime weights shift automatically based on market conditions. US uses 4-state HMM; India uses India VIX heuristics (VIX > 25 = Bear, > 18 = Late-Cycle, else Risk-On).

---

## Alert System

Users can subscribe to three alert types per ticker:

| Alert Type | Trigger |
|---|---|
| **Score Change** | Composite score delta >= min_delta (default 0.10) |
| **Regime Change** | Market regime shifts between Risk-On / Late-Cycle / Bear / Recovery |
| **Threshold** | Composite score crosses a user-defined threshold |

Alerts are delivered via email (Resend) with a 4-hour dedup window. Subscriptions and delivery history are stored in Supabase with RLS enforcement.

---

## Real-Time Streaming

`GET /stocks/{ticker}/stream?market=US` — SSE endpoint emitting score updates every 30 seconds. Client connects with `EventSource` and receives `score` events with full AIScore JSON payloads, plus `heartbeat` events when no change.

---

## Repository Layout

```
stockpredictor/
├── packages/
│   ├── data/                  # nq-data: connectors, DataBroker, DuckDB store
│   │   └── src/nq_data/
│   │       ├── broker.py            # DataBroker (unified fetch interface)
│   │       ├── store.py             # DuckDB-backed DataStore
│   │       ├── models.py            # Pydantic domain models
│   │       ├── price/               # yfinance + NSE Bhavcopy connectors
│   │       ├── macro/               # FRED macro connector
│   │       └── alt_signals/         # EDGAR Form 4 insider trades
│   └── signals/               # nq-signals: 5-factor engine + ranking
│       └── src/nq_signals/
│           ├── engine.py            # SignalEngine — 5-factor composite (US + IN)
│           ├── factors/             # Quality, Momentum, Value, Low-Vol computation
│           ├── regime/              # 4-state HMM market regime detector
│           └── ranker/              # LightGBM LambdaRank + walk-forward BT
├── apps/
│   ├── api/                   # nq-api v4.0.0: FastAPI backend
│   │   └── src/nq_api/
│   │       ├── main.py              # FastAPI app, CORS, startup prewarm
│   │       ├── schemas.py           # Pydantic v2 models
│   │       ├── schemas_alerts.py    # Alert subscription/delivery schemas
│   │       ├── data_builder.py      # 100% live data (US + IN macro + Bhavcopy)
│   │       ├── score_builder.py     # DataFrame -> AIScore + rank-based 1-10
│   │       ├── alert_checker.py    # Background alert evaluation + email dispatch
│   │       ├── notify.py            # Resend email delivery
│   │       ├── routes/
│   │       │   ├── stocks.py        # GET /stocks/{ticker} + /chart + /meta + /stream (SSE)
│   │       │   ├── screener.py      # POST /screener
│   │       │   ├── analyst.py       # POST /analyst (PARA-DEBATE)
│   │       │   ├── query.py         # POST /query (self-aware NL, multi-turn)
│   │       │   ├── market.py        # GET /market/*
│   │       │   ├── alerts.py        # GET/POST/DELETE /alerts/subscriptions + /deliveries
│   │       │   └── watchlists.py    # /watchlist CRUD
│   │       └── agents/              # 7-agent PARA-DEBATE system
│   └── web/                   # Next.js 16 frontend (Obsidian Quantum)
│       └── src/
│           ├── app/
│           │   ├── page.tsx         # Landing page
│           │   ├── dashboard/       # Market dashboard
│           │   ├── screener/         # AI screener table
│           │   ├── stocks/[ticker]/ # Stock detail + SSE live updates
│           │   ├── query/           # Ask AI (NL query)
│           │   ├── backtest/        # Strategy backtest
│           │   ├── alerts/          # Alert management
│           │   └── watchlist/       # Watchlist
│           └── components/          # UI components (Glass, GhostBorder, GradientButton)
└── apps/api/migrations/        # Supabase SQL migrations (001-004)
```

---

## Quickstart

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) — fast Python package manager
- Node.js 20+ (for frontend)
- [FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html) (free)
- [Anthropic API key](https://console.anthropic.com/) (for PARA-DEBATE + NL query)

### 1. Clone & install

```bash
git clone https://github.com/satyamdas03/NeuralQuant.git
cd NeuralQuant
uv sync
```

### 2. Configure environment

```bash
# apps/api/.env
ANTHROPIC_API_KEY=sk-ant-...
FRED_API_KEY=your_fred_key_here
RESEND_API_KEY=re_...         # optional — alerts log instead of email if missing
RESEND_FROM=NeuralQuant <alerts@neuralquant.ai>
```

### 3. Start the API

```bash
cd apps/api
# Windows
..\..\.venv\Scripts\python.exe -m uvicorn nq_api.main:app --reload --port 8000

# Mac/Linux
../../.venv/bin/uvicorn nq_api.main:app --reload --port 8000
```

API live at `http://localhost:8000` · Swagger docs at `/docs`

### 4. Start the frontend

```bash
cd apps/web
npm install
npm run dev    # http://localhost:3000
```

### 5. Run tests

```bash
.venv/Scripts/pytest.exe apps/api/tests/ packages/ -v
```

---

## API Reference

### `GET /health`
```json
{ "status": "ok", "version": "4.1.0" }
```

### `GET /stocks/{ticker}?market=US`
Returns AI score (1-10) with 5 sub-scores, regime, feature attribution, and rank-normalised 1-10 score.

### `GET /stocks/{ticker}/stream?market=US`
SSE endpoint — emits `score` events every 30s when the score changes, `heartbeat` otherwise.

### `GET /stocks/{ticker}/chart?period=1mo`
OHLCV price history. Periods: `1d` `5d` `1mo` `3mo` `1y` `5y`

### `GET /stocks/{ticker}/meta`
Live price, market cap, P/E, P/B, beta, 52-week range, earnings date, analyst target.

### `POST /screener`
Rank a universe by AI score. Scores spread across 1-10 via rank-based percentile mapping.

### `POST /analyst`
Run full **PARA-DEBATE** — 6 specialists run in parallel, HEAD ANALYST synthesises.

### `POST /query`
Multi-turn NL query grounded in live scores, FRED macro, and news.

### `GET /alerts/subscriptions`
List user's alert subscriptions (auth required).

### `POST /alerts/subscriptions`
Create alert: score_change, regime_change, or threshold (auth required).

### `GET /alerts/deliveries`
List recent alert deliveries (auth required).

---

## Roadmap

### Phase 1 ✅ — Quantitative Signal Engine
- [x] DataBroker + DuckDB DataStore
- [x] yfinance + NSE Bhavcopy connectors
- [x] FRED macro + EDGAR Form 4 connectors
- [x] Quality, Momentum, Short-interest factors
- [x] 4-regime HMM detector
- [x] LightGBM LambdaRank signal combiner
- [x] Walk-forward backtester with IC/ICIR metrics
- [x] 33 tests, fully validated

### Phase 2 ✅ — AI Analyst Platform
- [x] FastAPI backend (health, stocks, screener, analyst, query, market)
- [x] Pydantic v2 schemas + rank-based score builder (feature attribution)
- [x] 7-agent PARA-DEBATE system (6 specialists + HEAD ANALYST)
- [x] Next.js 16 frontend — Obsidian Quantum design system

### Phase 3 ✅ — 100% Live Data + Quality
- [x] Replace all synthetic data with real yfinance + FRED pipeline
- [x] Value factor (P/E + P/B cross-sectional rank)
- [x] Low-volatility factor (realized vol + beta rank)
- [x] FRED integration: HY spread, CPI, Fed funds, 2Y/10Y yields
- [x] Score compression fix — rank-based 1-10 mapping
- [x] Query engine self-awareness — cites live NeuralQuant scores

### Phase 4 ✅ — Production Features
- [x] Supabase auth, tiers, rate limiting
- [x] Watchlist (server-side Supabase)
- [x] Alert system (Resend email on score/regime/threshold changes)
- [x] Real-time SSE score streaming
- [x] Sector-adjusted quality scoring
- [x] EDGAR Form 4 insider signals wired into composite
- [x] India NSE Bhavcopy wired for realtime IN scores
- [x] delivery_pct signal for IN market
- [x] India VIX regime heuristics
- [x] Obsidian Quantum UI redesign

### Phase 4.1 ✅ — Quality Upgrade (v4.1.0)
- [x] FinnhubClient with token bucket rate limiting + in-process cache
- [x] Technical agent: RSI-14, MACD, ATR-14, SMA-50/200, volume ratio, crash protection
- [x] Sentiment agent: real insider cluster scores (not hardcoded 0.5), news sentiment, short interest
- [x] Fundamental agent: ROE, revenue growth, D/E, sector median comparison
- [x] Head analyst weight fix: 125% → 100%, raw data cross-reference fields
- [x] Adversarial agent: individual specialist outputs for targeted challenge
- [x] India macro context: India VIX, RBI repo rate, INR/USD, Nifty vs 200MA
- [x] Ask AI: Finnhub news summaries in all 3 endpoints
- [x] Sector peer comparison: medians for P/E, ROE, margin, D/E, composite
- [x] Persistent conversation memory: Supabase `conversations` table with RLS
- [x] DEEP route enrichment: Finnhub, India macro, sector medians now in all query paths

### Phase 5 🔮 — Next
- [ ] Fitted HMM for India market regime detection
- [ ] Reddit/StockTwits sentiment integration
- [ ] Portfolio construction (sized baskets with return bands)
- [ ] Stripe Checkout + billing webhook
- [ ] Mobile PWA support
- [ ] WebSocket upgrade for full-duplex streaming

---

## Contributing

Pull requests welcome. Please:
1. Run `pytest` from the repo root — all tests must pass
2. Follow the existing code style (Ruff-compatible, Pydantic v2)
3. Keep agent prompts in `agents/*.py` — don't hardcode in routes
4. No synthetic data — every new data field must come from a real source

---

## License

MIT — see [LICENSE](LICENSE).

---

<div align="center">
Built with Claude Sonnet 4.6 · 5-Factor Quant Engine · 7-Agent PARA-DEBATE · Finnhub Enrichment · India & US Markets · 100% Live Data
</div>
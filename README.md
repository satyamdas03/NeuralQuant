<div align="center">

# NeuralQuant

**AI-Powered Stock Intelligence Platform — v4.0.0-dev (Pillars A1 + A2 + B live)**

*Institutional-grade quant research + 7-agent AI debate. US & India. 100% live data.*

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black?logo=nextdotjs)](https://nextjs.org)
[![Claude Sonnet 4.6](https://img.shields.io/badge/Claude-Sonnet%204.6-orange?logo=anthropic&logoColor=white)](https://anthropic.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-33%2B%20passing-brightgreen)](apps/api/tests)
[![Data](https://img.shields.io/badge/data-100%25%20live-brightgreen)](#data-sources)

</div>

---

## Phase 4 Progress (v4.0.0-dev)

| Pillar | Scope | Status |
|---|---|---|
| **A1** | Supabase auth, watchlists, tiers (free/investor/pro/api) | ✅ LIVE — schema applied (migrations 001-003), API + web deployed |
| **A2** | Per-tier rate limiting via `public.usage_log` | ✅ LIVE — `/query` `/analyst` `/screener` gated (Stripe deferred) |
| **B** | 503 US (S&P 500) + 200 NSE (Nifty 200) universe, sector-adjusted factor ranks, nightly `score_cache` | ✅ LIVE — schema applied (migration 004), nightly GHA cron `0 2 * * *` |
| **C** | Fitted HMM, ISM PMI, Reddit/StockTwits sentiment | Plan written ([spec](docs/superpowers/plans/2026-04-18-pillar-c-hmm-pmi-sentiment.md)) |
| **D** | backtrader-based backtesting engine | Plan written ([spec](docs/superpowers/plans/2026-04-18-pillar-d-backtesting.md)) |
| **Stripe** | Checkout + billing webhook | Deferred — will wire up at end |

**Live deploys:**
- API (Render): `https://neuralquant.onrender.com`
- Web (Vercel): `https://neuralquant.vercel.app`

**Ask AI bug fixes (Apr 17-18, 2026):** Portfolio responses now honour user-specified return bands (targets computed as entry × (1 + r%) with r inside band), scenarios align with band, Indian portfolios no longer truncate at COALINDIA (max_tokens 1500 → 4000, parser cap 3000 → 8000), screener pool 25 → 40, currency rule clarified (allocation currency = user capital, price currency = native).

**Supabase migrations applied:** `001_init_auth_watchlists`, `002_handle_new_user_search_path`, `003_rls_initplan_optimize`, `004_score_cache` (all live in `public` schema; RLS policies wrap `auth.uid()` in subselects; security + performance advisors clean).

**Env keys (Render + Vercel configured via API):** `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `SUPABASE_ANON_KEY`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL`, `FRED_API_KEY`, `ANTHROPIC_API_KEY`.

**GHA secrets:** `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `FRED_API_KEY` — set via `gh secret set` for nightly-score workflow.

---

## What is NeuralQuant?

NeuralQuant is a full-stack AI stock intelligence platform that combines a **5-factor quantitative signal engine** with a **7-agent AI analyst debate system** (PARA-DEBATE) to deliver institutional-grade research at retail speed — backed entirely by **live, real data**.

- **Ask in plain English.** *"Is NVDA a buy right now?"* — get a structured answer citing NeuralQuant's own live score (9/10), P/E, price vs. analyst target, and FRED macro conditions.
- **See every reason.** Danelfin-style feature attribution shows the exact factors (Quality, Momentum, Value, Low-Vol, Short Interest) driving each AI score.
- **India + US, day one.** Full 5-factor AI scoring for 50 NSE stocks alongside 50 NYSE/NASDAQ names.
- **7 agents, one verdict.** MACRO, FUNDAMENTAL, TECHNICAL, SENTIMENT, GEOPOLITICAL, and ADVERSARIAL specialists debate in parallel; the HEAD ANALYST synthesises the conviction call.
- **Zero synthetic data.** Every score, every macro figure, every news headline is pulled from live sources — FRED, yfinance, Yahoo Finance news.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Next.js 15 Frontend                           │
│  Market Dashboard · AIScoreCard · FeatureAttribution (5 factors)    │
│  AgentDebatePanel · NL Query (multi-turn) · Price Charts            │
└────────────────────────┬────────────────────────────────────────────┘
                         │ REST / JSON
┌────────────────────────▼────────────────────────────────────────────┐
│                      FastAPI (nq-api v3.0.0)                         │
│  GET  /stocks/{ticker}        GET /stocks/{ticker}/chart             │
│  GET  /stocks/{ticker}/meta   POST /screener                         │
│  POST /analyst                POST /query (multi-turn)               │
│  GET  /market/overview        GET  /market/sectors                   │
│  GET  /market/news            GET  /market/movers                    │
│  GET  /market/data-quality                                           │
└──────────┬──────────────────────┬───────────────────────────────────┘
           │                      │
┌──────────▼──────────┐  ┌────────▼──────────────────────────────────┐
│  nq-signals engine  │  │        PARA-DEBATE Orchestrator             │
│  ─────────────────  │  │  ────────────────────────────────────────  │
│  HMM Regime (4)     │  │  MACRO        ─┐                           │
│  LightGBM LambdaRnk │  │  FUNDAMENTAL  ├─ asyncio.gather()          │
│  Quality / Momentum │  │  TECHNICAL    │   (all 6 in parallel)      │
│  Value (P/E + P/B)  │  │  SENTIMENT    │                            │
│  Low-Volatility     │  │  GEOPOLITICAL ├──► HEAD ANALYST            │
│  Short Interest     │  │  ADVERSARIAL  ┘    (synthesis + verdict)   │
│  Walk-Forward BT    │  └────────────────────────────────────────────┘
└──────────┬──────────┘
┌──────────▼──────────┐
│    nq-data layer    │
│  ─────────────────  │
│  yfinance (US/IN)   │   Live prices, OHLCV, fundamentals, news
│  NSE Bhavcopy (IN)  │   India market data
│  FRED API (macro)   │   HY Spread, CPI, Fed Funds, 2Y/10Y yields
│  EDGAR Form 4       │   Insider buying/selling signals
│  DuckDB DataStore   │   Zero-copy columnar cache
└─────────────────────┘
```

---

## Data Sources

Every number shown in NeuralQuant is sourced from live APIs — no synthetic data, no stale snapshots.

| Data Point | Source | Refresh |
|---|---|---|
| VIX level | yfinance `^VIX` | Real-time |
| S&P 500 vs 200-day MA | yfinance `^GSPC` | Real-time |
| SPX 1-month return | yfinance `^GSPC` | Real-time |
| HY Credit Spread OAS | FRED `BAMLH0A0HYM2` | Daily |
| CPI YoY inflation | FRED `CPIAUCSL` | Monthly |
| Fed Funds Rate | FRED `FEDFUNDS` | Monthly |
| 10-year Treasury yield | FRED `DGS10` | Daily |
| 2-year Treasury yield | FRED `DGS2` | Daily |
| Gross profit margin | yfinance `grossMargins` | Quarterly |
| Piotroski F-score (0–9) | yfinance financials | Quarterly |
| Accruals ratio | yfinance (NI − OCF) / TA | Quarterly |
| 12-1 month momentum | yfinance 14-month OHLCV | Daily |
| Realized 1Y volatility | yfinance price history | Daily |
| P/E TTM | yfinance `trailingPE` | Real-time |
| P/B ratio | yfinance `priceToBook` | Real-time |
| Beta | yfinance `beta` | Real-time |
| Short interest % float | yfinance `shortPercentOfFloat` | Bi-weekly |
| Live stock price | yfinance info | Real-time |
| 52-week high/low | yfinance info | Real-time |
| Analyst price target | yfinance `targetMeanPrice` | As published |
| Market news headlines | Yahoo Finance news feed | Real-time |
| Sector performance | yfinance sector ETFs | Real-time |
| Gainers / losers / active | yfinance market data | Real-time |

---

## Feature Highlights

| Feature | Benchmark | Our advantage |
|---|---|---|
| **5-factor AI scoring** | Danelfin (3 factors) | Quality + Momentum + Value (P/E+P/B) + Low-Vol + Short Interest |
| **NL query — self-aware** | Perplexity Finance | Answers cite live NeuralQuant scores: *"NVDA scores 9/10, P/E 34.9x at $171"* |
| **7-agent debate (PARA-DEBATE)** | FactSet Mercury ($15k/yr) | 6 specialist agents + HEAD ANALYST via Claude Sonnet 4.6 |
| **India + US coverage** | SimplyWall.St (US-heavy) | Full 5-factor scoring for 50 NSE stocks from day one |
| **Live macro context** | None at retail | FRED-sourced CPI, HY spreads, yield curve injected into every query |
| **Explainability** | Danelfin | Per-factor contribution bars + regime-aware weighting |
| **Multi-turn NL chat** | Perplexity Finance | Conversation history, platform data injected each turn |

---

## The 5-Factor Model

Scores are computed cross-sectionally within a 50-stock reference universe — **no hardcoded thresholds**, everything is relative.

| Factor | Signal | Weight (Risk-On) |
|---|---|---|
| **Quality** | Gross margin + Piotroski F-score + Accruals ratio | 25% |
| **Momentum** | 12-1 month price return (Jegadeesh-Titman) | 30% |
| **Value** | Inverse of (P/E rank × 0.5 + P/B rank × 0.5) | 10% |
| **Low Volatility** | Inverse of realized 1Y vol + beta rank | 15% |
| **Low Short Interest** | Inverse of short float rank | 15% |

Regime weights shift automatically based on the 4-state HMM (Risk-On → Late-Cycle → Bear → Recovery).

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
│   │       ├── macro/               # FRED macro connector (HY, CPI, yields, PMI)
│   │       └── alt_signals/         # EDGAR Form 4 insider trades
│   └── signals/               # nq-signals: 5-factor engine + ranking
│       └── src/nq_signals/
│           ├── engine.py            # SignalEngine — 5-factor composite scorer
│           ├── factors/             # Quality, Momentum, Value, Low-Vol computation
│           ├── regime/              # 4-state HMM market regime detector
│           └── ranker/              # LightGBM LambdaRank + walk-forward BT
├── apps/
│   ├── api/                   # nq-api v3.0.0: FastAPI backend
│   │   └── src/nq_api/
│   │       ├── main.py              # FastAPI app, CORS, startup prewarm
│   │       ├── schemas.py           # Pydantic v2 models (multi-turn QueryRequest, etc.)
│   │       ├── deps.py              # Singleton engine dependency
│   │       ├── score_builder.py     # DataFrame → AIScore + rank-based 1-10 scoring
│   │       ├── data_builder.py      # 100% live data pipeline (FRED + yfinance)
│   │       ├── universe.py          # 50 US + 50 India default universes
│   │       ├── routes/
│   │       │   ├── stocks.py        # GET /stocks/{ticker} + /chart + /meta
│   │       │   ├── screener.py      # POST /screener (rank-based scoring)
│   │       │   ├── analyst.py       # POST /analyst (PARA-DEBATE)
│   │       │   ├── query.py         # POST /query (self-aware NL, multi-turn)
│   │       │   └── market.py        # GET /market/* (overview, sectors, news, movers)
│   │       └── agents/
│   │           ├── base.py          # BaseAnalystAgent (Claude SDK + retries)
│   │           ├── macro.py         # MACRO specialist
│   │           ├── fundamental.py   # FUNDAMENTAL specialist
│   │           ├── technical.py     # TECHNICAL specialist
│   │           ├── sentiment.py     # SENTIMENT specialist
│   │           ├── geopolitical.py  # GEOPOLITICAL specialist
│   │           ├── adversarial.py   # ADVERSARIAL (permanent bear)
│   │           └── orchestrator.py  # HEAD ANALYST + asyncio parallel runner
│   └── web/                   # Next.js 15 frontend
│       └── src/app/
│           ├── page.tsx             # Market dashboard (indices, sectors, news, movers)
│           ├── screener/            # AI screener table with factor breakdown
│           ├── stocks/[ticker]/     # Stock detail (price chart, score card, PARA-DEBATE)
│           └── query/               # Multi-turn NL query interface
└── docs/
    └── superpowers/plans/     # Implementation specs and design docs
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

On first start, 20 US tickers are pre-warmed in the background (~15–25 s). Subsequent requests use the 4-hour cache.

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
{ "status": "ok", "version": "3.0.0" }
```

### `GET /stocks/{ticker}?market=US`
Returns AI score (1–10) with 5 sub-scores, regime, feature attribution, and rank-normalised 1-10 score within the reference universe.

```json
{
  "ticker": "NVDA",
  "market": "US",
  "score_1_10": 9,
  "composite_score": 0.523,
  "regime_label": "Risk-On",
  "confidence": "medium",
  "sub_scores": {
    "quality": 0.47,
    "momentum": 0.95,
    "value": 0.18,
    "low_vol": 0.34,
    "short_interest": 0.82
  },
  "top_drivers": [
    { "name": "12-1 Momentum",     "contribution": 0.90, "direction": "positive" },
    { "name": "Low Short Interest", "contribution": 0.64, "direction": "positive" },
    { "name": "Value (P/E + P/B)", "contribution": -0.64, "direction": "negative" }
  ],
  "last_updated": "2026-03-27T10:00:00+00:00"
}
```

### `GET /stocks/{ticker}/chart?period=1mo`
OHLCV price history. Periods: `1d` `5d` `1mo` `3mo` `1y` `5y`

### `GET /stocks/{ticker}/meta`
Live price, market cap, P/E, P/B, beta, 52-week range, earnings date, analyst target.

### `POST /screener`
Rank a universe by AI score. Scores spread across 1–10 via rank-based percentile mapping.

```json
// Request
{ "market": "US", "max_results": 20 }

// Response
{
  "regime_label": "Risk-On",
  "results": [
    { "ticker": "JNJ", "score_1_10": 10, "confidence": "high", ... },
    { "ticker": "GOOGL", "score_1_10": 10, ... },
    ...
  ]
}
```

### `POST /analyst`
Run full **PARA-DEBATE** — 6 specialists run in parallel, HEAD ANALYST synthesises.

```json
// Request
{ "ticker": "AAPL", "market": "US" }

// Response
{
  "ticker": "AAPL",
  "head_analyst_verdict": "HOLD",
  "investment_thesis": "AAPL holds a strong ecosystem moat...",
  "bull_case": "...",
  "bear_case": "...",
  "risk_factors": ["...", "..."],
  "agent_outputs": [
    { "agent": "MACRO",       "stance": "BULL", "conviction": "HIGH", "thesis": "..." },
    { "agent": "ADVERSARIAL", "stance": "BEAR", "conviction": "MEDIUM", "thesis": "..." }
  ],
  "consensus_score": 0.62
}
```

### `POST /query`
Multi-turn NL query grounded in live scores, FRED macro, and news. The engine auto-fetches NeuralQuant scores for any mentioned ticker.

```json
// Request
{
  "question": "Is NVDA a buy?",
  "market": "US",
  "history": []
}

// Response
{
  "answer": "NeuralQuant rates NVDA 9/10 (medium confidence). P/E of 34.9x is expensive (18th percentile value rank), but momentum is at the 95th percentile...",
  "data_sources": ["NeuralQuant Screener", "Live Prices", "FRED Macro", "Live News"],
  "follow_up_questions": ["...", "...", "..."]
}
```

### `GET /market/overview`
Live S&P 500, NASDAQ, Dow Jones, VIX with price, change, and mini-chart data.

### `GET /market/sectors`
11 GICS sector performance via sector ETFs (XLK, XLE, XLF, ...).

### `GET /market/news`
Live market news headlines from Yahoo Finance.

### `GET /market/movers`
Top gainers, losers, and most active stocks with live prices and volume.

### `GET /market/data-quality`
Full transparency: how many tickers are live vs synthetic, complete FRED macro snapshot.

---

## Signal Engine

The quantitative backbone — **33 tests passing**, walk-forward validated:

| Component | Description |
|---|---|
| **DataBroker** | Unified interface over yfinance, NSE Bhavcopy, FRED, EDGAR |
| **DuckDB DataStore** | Zero-copy columnar storage for tick + fundamental data |
| **Quality Factor** | Gross margin + Piotroski F-score (0–9) + Accruals ratio |
| **Momentum Factor** | 12-1 month price momentum (Jegadeesh-Titman, crash-protected) |
| **Value Factor** | P/E + P/B cross-sectional inverse rank |
| **Low-Volatility Factor** | Realized 1Y vol + beta inverse rank |
| **Short Interest** | Low short-float percentile (contrarian signal, correctly inverted) |
| **HMM Regime** | 4-state hidden Markov model: Risk-On / Late-Cycle / Bear / Recovery |
| **LightGBM LambdaRank** | Learning-to-rank signal combiner with NDCG objective |
| **Walk-Forward BT** | Rolling IC, ICIR, and hit-rate validation across regimes |

---

## PARA-DEBATE Protocol

Six specialist agents run **in parallel** via `asyncio.gather`, receiving live FRED macro + stock scores:

```
MACRO ──────────────────────────────────────────────┐
FUNDAMENTAL (with P/E, P/B, Piotroski, accruals) ───┤
TECHNICAL (with momentum, realized vol, beta) ───────┼──► HEAD ANALYST ──► Verdict
SENTIMENT ───────────────────────────────────────────┤         │            BUY / HOLD / SELL
GEOPOLITICAL ────────────────────────────────────────┤         └──► 4–6 sentence synthesis
ADVERSARIAL (always BEAR/NEUTRAL — devil's advocate) ┘
```

Each agent receives: ticker score, all 5 factor percentiles, full FRED macro snapshot (VIX, CPI, HY spread, yield curve, ISM PMI, Fed rate), regime label, and live news headlines.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Signal engine | Python 3.12, LightGBM, hmmlearn, pandas, DuckDB |
| API | FastAPI 0.115, Pydantic v2, uvicorn |
| AI agents | Anthropic Claude Sonnet 4.6 |
| Data — live prices | yfinance |
| Data — macro | FRED API (fredapi) |
| Data — news | Yahoo Finance news feed (via yfinance) |
| Frontend | Next.js 15 App Router, Tailwind CSS, shadcn/ui, Recharts |
| Package mgmt | uv workspace monorepo |
| Deploy (target) | Vercel (frontend) · Railway (API) |

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
- [x] PARA-DEBATE orchestrator (parallel asyncio)
- [x] Next.js 15 frontend — market dashboard, screener, stock detail, NL query
- [x] Price charts (1D/1W/1M/3M/1Y), sector heatmap, gainers/losers

### Phase 3 ✅ — 100% Live Data + Quality
- [x] Replace all synthetic data with real yfinance + FRED pipeline
- [x] Value factor (P/E + P/B cross-sectional rank)
- [x] Low-volatility factor (realized vol + beta rank)
- [x] FRED integration: HY spread, CPI, Fed funds, 2Y/10Y yields
- [x] Score compression fix — rank-based 1–10 mapping across universe
- [x] Short interest display fix — correctly shows as bullish for low-float stocks
- [x] Invalid ticker → HTTP 404 (not fabricated scores)
- [x] Query engine self-awareness — cites live NeuralQuant scores in every answer
- [x] Multi-turn NL conversation with history
- [x] Full macro context injected into every analyst debate and NL query

### Phase 4 🔮 — Production Features
- [ ] User auth (Supabase)
- [ ] Watchlist + portfolio construction
- [ ] Real-time score streaming (WebSocket)
- [ ] Alert system (email + push on score changes)
- [ ] Sector-adjusted quality scoring (financials use ROE/NIM instead of margins)
- [ ] EDGAR Form 4 insider signals wired to scoring
- [ ] India NSE Bhavcopy wired for real-time IN scores

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
Built with Claude Sonnet 4.6 · 5-Factor Quant Engine · India & US Markets · 100% Live Data
</div>

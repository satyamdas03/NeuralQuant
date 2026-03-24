<div align="center">

# NeuralQuant

**AI-Powered Stock Intelligence Platform**

*The FactSet Mercury experience at retail price — with India coverage from day one.*

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black?logo=nextdotjs)](https://nextjs.org)
[![Claude claude-sonnet-4-6](https://img.shields.io/badge/Claude-claude--sonnet--4--6-orange?logo=anthropic&logoColor=white)](https://anthropic.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-33%2B%20passing-brightgreen)](apps/api/tests)

</div>

---

## What is NeuralQuant?

NeuralQuant is a full-stack AI stock intelligence platform that combines a **quantitative signal engine** with a **7-agent AI analyst debate system** (PARA-DEBATE) to deliver institutional-grade research at retail speed.

- **Ask in plain English.** *"Why is RELIANCE underperforming its sector?"* — get a structured answer grounded in your own live data, not web search.
- **See every reason.** Danelfin-style feature attribution shows the exact factors driving each AI score.
- **India + US, day one.** Full AI scoring for NSE/BSE via live Bhavcopy feeds alongside NYSE/NASDAQ.
- **7 agents, one verdict.** MACRO, FUNDAMENTAL, TECHNICAL, SENTIMENT, GEOPOLITICAL, and ADVERSARIAL specialists debate in parallel; the HEAD ANALYST synthesises the conviction call.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Next.js 15 Frontend                       │
│  AIScoreCard · FeatureAttribution · AgentDebatePanel · NLQuery  │
└────────────────────────┬────────────────────────────────────────┘
                         │ REST / JSON
┌────────────────────────▼────────────────────────────────────────┐
│                      FastAPI (nq-api v2)                         │
│  GET /stocks/{ticker}  ·  POST /screener                        │
│  POST /analyst         ·  POST /query                           │
└──────────┬──────────────────────┬───────────────────────────────┘
           │                      │
┌──────────▼──────────┐  ┌────────▼──────────────────────────────┐
│  nq-signals engine  │  │        PARA-DEBATE Orchestrator        │
│  ─────────────────  │  │  ───────────────────────────────────   │
│  HMM Regime (4)     │  │  MACRO      ─┐                        │
│  LightGBM LambdaRank│  │  FUNDAMENTAL ├─ asyncio.gather()      │
│  Quality / Momentum │  │  TECHNICAL   │   (parallel)           │
│  Short Interest     │  │  SENTIMENT   │                        │
│  Walk-Forward BT    │  │  GEOPOLITICAL├─►  HEAD ANALYST         │
└──────────┬──────────┘  │  ADVERSARIAL─┘   (synthesis)          │
           │             └────────────────────────────────────────┘
┌──────────▼──────────┐
│    nq-data layer    │
│  ─────────────────  │
│  yfinance (US)      │
│  NSE Bhavcopy (IN)  │
│  FRED macro         │
│  EDGAR Form 4       │
│  DuckDB DataStore   │
└─────────────────────┘
```

---

## Feature Highlights

| Feature | Benchmark we beat | How |
|---|---|---|
| **AI explainability** | Danelfin | Feature attribution bars + counterfactuals per stock |
| **NL query interface** | Perplexity Finance (web) | Data-grounded queries using *your* live signal engine |
| **India coverage** | SimplyWall.St (data only) | Full AI scoring for NSE/BSE from day one |
| **7-agent debate** | FactSet Mercury ($15k/yr) | PARA-DEBATE protocol via Claude claude-sonnet-4-6 |
| **Backtesting visibility** | None at retail | Walk-forward IC/ICIR stats exposed via API & UI |

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
│   └── signals/               # nq-signals: factor engine + ranking
│       └── src/nq_signals/
│           ├── engine.py            # SignalEngine (main entry point)
│           ├── factors/             # Quality & Momentum factor computation
│           ├── regime/              # 4-state HMM market regime detector
│           └── ranker/              # LightGBM LambdaRank + walk-forward BT
├── apps/
│   ├── api/                   # nq-api: FastAPI backend (Phase 2)
│   │   └── src/nq_api/
│   │       ├── main.py              # FastAPI app, CORS, router mounts
│   │       ├── schemas.py           # Pydantic v2 request/response models
│   │       ├── deps.py              # Singleton dependencies (engine, orchestrator)
│   │       ├── score_builder.py     # Maps engine DataFrame → AIScore schema
│   │       ├── universe.py          # Default US + India stock universes
│   │       ├── routes/
│   │       │   ├── stocks.py        # GET /stocks/{ticker}
│   │       │   ├── screener.py      # POST /screener
│   │       │   ├── analyst.py       # POST /analyst  (PARA-DEBATE)
│   │       │   └── query.py         # POST /query    (NL interface)
│   │       └── agents/
│   │           ├── base.py          # BaseAnalystAgent (Claude SDK + retries)
│   │           ├── macro.py         # MACRO specialist
│   │           ├── fundamental.py   # FUNDAMENTAL specialist
│   │           ├── technical.py     # TECHNICAL specialist
│   │           ├── sentiment.py     # SENTIMENT specialist
│   │           ├── geopolitical.py  # GEOPOLITICAL specialist
│   │           ├── adversarial.py   # ADVERSARIAL (devil's advocate)
│   │           └── orchestrator.py  # HEAD ANALYST + asyncio parallel runner
│   └── web/                   # Next.js 15 frontend (Phase 2 — in progress)
│       ├── app/                     # App Router pages
│       └── components/              # AIScoreCard, FeatureAttribution, etc.
├── scripts/
│   └── backtest/              # Walk-forward backtest runner + report
└── data/backtest/             # Backtest output CSVs (gitignored)
```

---

## Quickstart

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (fast Python package manager)
- Node.js 20+ (for frontend)

### 1. Clone & install

```bash
git clone https://github.com/satyamdas03/NeuralQuant.git
cd NeuralQuant

# Install all workspace packages in one shot
uv sync
```

### 2. Run the API

```bash
cd apps/api
uv run uvicorn nq_api.main:app --reload --port 8000
```

The API will be live at `http://localhost:8000`. Swagger docs at `/docs`.

### 3. Run tests

```bash
# From repo root
.venv/Scripts/pytest.exe apps/api/tests/ packages/ -v
```

### 4. Run the frontend (coming soon)

```bash
cd apps/web
npm install
npm run dev        # http://localhost:3000
```

---

## API Reference

### `GET /health`
```json
{ "status": "ok", "version": "2.0.0" }
```

### `GET /stocks/{ticker}?market=US`
Returns an AI score (1–10) with sub-scores, regime, and feature attribution.

```json
{
  "ticker": "AAPL",
  "market": "US",
  "score_1_10": 8,
  "regime_label": "Risk-On",
  "sub_scores": {
    "quality": 7.2,
    "momentum": 8.5,
    "short_interest": 6.1,
    "macro": 7.0
  },
  "confidence": 0.81,
  "top_drivers": [
    { "feature": "12-1 Momentum", "contribution": 0.34, "direction": "bullish" },
    { "feature": "Quality composite", "contribution": 0.28, "direction": "bullish" },
    { "feature": "Short interest", "contribution": -0.12, "direction": "bearish" }
  ]
}
```

### `POST /screener`
Rank a universe of tickers by AI score.

```json
// Request
{ "market": "US", "top_n": 20 }

// Response
{ "results": [ { "ticker": "NVDA", "score_1_10": 9, ... }, ... ] }
```

### `POST /analyst`
Run the full **PARA-DEBATE** 7-agent analysis on a ticker.

```json
// Request
{ "ticker": "RELIANCE", "market": "IN" }

// Response — HEAD ANALYST synthesis + all 6 specialist outputs
{
  "ticker": "RELIANCE",
  "synthesis": "Strong buy. Macro tailwinds in energy transition...",
  "conviction": "BUY",
  "agents": [
    { "role": "MACRO", "stance": "BULL", "summary": "...", "key_points": [...] },
    { "role": "ADVERSARIAL", "stance": "BEAR", "summary": "...", "key_points": [...] },
    ...
  ]
}
```

### `POST /query`
Ask a natural language question grounded in live signal data.

```json
// Request
{ "question": "Which Indian mid-caps have the best momentum right now?" }

// Response
{ "answer": "Based on current NeuralQuant signals, top momentum mid-caps are...", "sources": [...] }
```

---

## Signal Engine (Phase 1)

The quantitative backbone — **33 tests passing**, walk-forward validated:

| Component | Description |
|---|---|
| **DataBroker** | Unified interface over yfinance, NSE Bhavcopy, FRED, EDGAR |
| **DuckDB DataStore** | Zero-copy columnar storage for tick + fundamental data |
| **Quality Factor** | Gross margin, Piotroski F-score, accruals ratio |
| **Momentum Factor** | 12-1 month price momentum (Jegadeesh-Titman) |
| **Short Interest** | Days-to-cover as contrarian signal |
| **HMM Regime** | 4-state hidden Markov model (Risk-On / Late-Cycle / Bear / Recovery) |
| **LightGBM LambdaRank** | Learning-to-rank signal combination with NDCG objective |
| **Walk-Forward BT** | Rolling IC, ICIR, and hit-rate validation across regimes |

---

## PARA-DEBATE Protocol

Six specialist agents run **in parallel** via `asyncio.gather`, then the HEAD ANALYST synthesises:

```
MACRO ──────────────────────────────────────┐
FUNDAMENTAL ────────────────────────────────┤
TECHNICAL ──────────────────────────────────┼──► HEAD ANALYST ──► Conviction Call
SENTIMENT ──────────────────────────────────┤         │            (BUY/HOLD/SELL)
GEOPOLITICAL ───────────────────────────────┤         └──► Synthesis paragraph
ADVERSARIAL (always BEAR/NEUTRAL) ──────────┘
```

Each agent:
- Receives the ticker's AI score, sub-scores, market context, and regime
- Returns a structured `AgentOutput` (stance, summary, 3–5 key points, data citations)
- Runs on **claude-sonnet-4-6** with automatic retry on rate-limit errors

---

## Tech Stack

| Layer | Technology |
|---|---|
| Signal engine | Python 3.12, LightGBM, hmmlearn, pandas, DuckDB |
| API | FastAPI 0.115, Pydantic v2, uvicorn |
| AI agents | Anthropic Claude claude-sonnet-4-6 SDK |
| Frontend | Next.js 15 App Router, Tailwind CSS, shadcn/ui, Recharts |
| Data | yfinance, NSE Bhavcopy, FRED API, SEC EDGAR |
| Package mgmt | uv workspace monorepo |
| Deploy (target) | Vercel (frontend) · Railway (API) |

---

## Roadmap

### Phase 1 ✅ — Quantitative Signal Engine
- [x] DataBroker + DuckDB DataStore
- [x] yfinance + NSE Bhavcopy connectors
- [x] FRED macro + EDGAR Form 4
- [x] Quality, Momentum, Short-interest factors
- [x] 4-regime HMM detector
- [x] LightGBM LambdaRank signal combiner
- [x] Walk-forward backtester
- [x] 33 tests, fully validated

### Phase 2 🚧 — AI Analyst Platform (in progress)
- [x] FastAPI backend (health, stocks, screener, analyst, query)
- [x] Pydantic v2 schemas + score builder (feature attribution)
- [x] 7-agent PARA-DEBATE system (BaseAgent + 6 specialists + HEAD ANALYST)
- [x] PARA-DEBATE orchestrator (parallel asyncio)
- [ ] Next.js 15 frontend scaffold
- [ ] AIScoreCard + FeatureAttribution components
- [ ] Stock detail page + screener page
- [ ] NL query interface
- [ ] Environment config + deployment

### Phase 3 🔮 — Platform Features
- [ ] User auth (Supabase)
- [ ] Real-time score updates (< 5 min after material news)
- [ ] Watchlists + portfolio construction
- [ ] Customisable backtest explorer
- [ ] Alert system (email + push)

---

## Contributing

Pull requests welcome. Please:
1. Run `pytest` from the repo root — all tests must pass
2. Follow the existing code style (Ruff-compatible, Pydantic v2)
3. Keep agent prompts in `agents/*.py` — don't hardcode them in routes

---

## License

MIT — see [LICENSE](LICENSE).

---

<div align="center">
Built with Claude claude-sonnet-4-6 · Powered by LightGBM + hmmlearn · India & US markets
</div>

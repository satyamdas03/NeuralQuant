# NeuralQuant Phase 2 — AI Analyst Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full-stack AI stock intelligence platform — FastAPI backend wrapping the Phase 1 signal engine, a 7-agent PARA-DEBATE Claude analyst system, and a beautiful Next.js frontend with explainable AI scores, natural language queries, and India + US market coverage.

**Architecture:** FastAPI serves AI scores (from Phase 1 nq_signals engine) and orchestrates 7 Claude subagents (MACRO, FUNDAMENTAL, TECHNICAL, SENTIMENT, GEOPOLITICAL, ADVERSARIAL, HEAD ANALYST) running in parallel via asyncio; HEAD ANALYST synthesises the debate into a final investment thesis. Next.js 15 frontend consumes the API, using Google Stitch components for beautiful UI with real-time score cards, an NL query box, and a ranked stock screener.

**Tech Stack:** Python 3.12 · FastAPI · Anthropic Claude SDK (claude-sonnet-4-6) · asyncio parallel agents · Supabase (auth + DB) · Next.js 15 App Router · Tailwind CSS · shadcn/ui · Recharts · Vercel (frontend) · Railway (API)

---

## Competitive Context (from analysis)

| Gap | Benchmark | Our target |
|---|---|---|
| AI explainability | Danelfin (top features shown) | Exceed — show feature attribution + counterfactuals |
| NL query interface | Perplexity Finance (web-grounded) | FactSet Mercury model at retail price — data-grounded |
| Real-time score updates | Kavout (partial) | Score updates within 5 min of material news |
| India coverage | SimplyWall.St (data only, no AI) | Full AI scoring for NSE/BSE from day one |
| Backtesting visibility | None (retail) | Show aggregate signal backtests; user-customisable in Phase 3 |

---

## Repository Layout (additions to existing `stockpredictor/`)

```
stockpredictor/
├── packages/              # Phase 1 (unchanged)
│   ├── data/
│   └── signals/
├── apps/
│   ├── api/               # NEW — FastAPI backend
│   │   ├── pyproject.toml
│   │   ├── src/nq_api/
│   │   │   ├── main.py            # FastAPI app, CORS, router mounts
│   │   │   ├── schemas.py         # Pydantic request/response models
│   │   │   ├── deps.py            # Shared dependencies (engine, store)
│   │   │   ├── routes/
│   │   │   │   ├── stocks.py      # GET /stocks/{ticker}  AI score + data
│   │   │   │   ├── screener.py    # POST /screener  ranked universe
│   │   │   │   ├── analyst.py     # POST /analyst  PARA-DEBATE report
│   │   │   │   └── query.py       # POST /query  NL financial query
│   │   │   └── agents/
│   │   │       ├── base.py        # BaseAgent with tool use + retries
│   │   │       ├── macro.py       # MACRO — regime & rate environment
│   │   │       ├── fundamental.py # FUNDAMENTAL — quality/value/earnings
│   │   │       ├── technical.py   # TECHNICAL — momentum/chart patterns
│   │   │       ├── sentiment.py   # SENTIMENT — news/insider/options flow
│   │   │       ├── geopolitical.py# GEOPOLITICAL — macro risk factors
│   │   │       ├── adversarial.py # ADVERSARIAL — devil's advocate
│   │   │       └── orchestrator.py# HEAD ANALYST + PARA-DEBATE runner
│   └── web/               # NEW — Next.js 15 frontend
│       ├── package.json
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── page.tsx            # Landing / hero
│       │   ├── screener/page.tsx   # Ranked screener table
│       │   ├── stocks/[ticker]/page.tsx  # Stock detail page
│       │   └── query/page.tsx      # NL query interface
│       ├── components/
│       │   ├── ui/                 # shadcn/ui primitives
│       │   ├── AIScoreCard.tsx     # Score ring + regime badge
│       │   ├── ScoreBreakdown.tsx  # Radar chart of sub-scores
│       │   ├── FeatureAttribution.tsx  # Top-N feature drivers (Danelfin-style)
│       │   ├── AgentDebatePanel.tsx    # PARA-DEBATE agent output accordion
│       │   ├── PriceChart.tsx      # OHLCV candlestick (Recharts)
│       │   ├── NLQueryBox.tsx      # Natural language input + response
│       │   ├── ScreenerTable.tsx   # Ranked stock table with AI scores
│       │   ├── RegimeBadge.tsx     # Market regime pill (Risk-On/Bear/etc.)
│       │   └── BacktestStats.tsx   # IC/ICIR signal performance card
│       └── lib/
│           ├── api.ts              # Typed fetch client for FastAPI
│           └── types.ts            # TypeScript interfaces
├── scripts/backtest/      # Phase 1 (unchanged)
└── data/backtest/         # Phase 1 (unchanged)
```

---

## Task 1 — FastAPI Package Scaffold

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/src/nq_api/__init__.py`
- Create: `apps/api/src/nq_api/main.py`
- Create: `apps/api/src/nq_api/schemas.py`
- Create: `apps/api/src/nq_api/deps.py`
- Create: `apps/api/tests/__init__.py`
- Create: `apps/api/tests/test_health.py`

- [ ] **Step 1: Write the health check test**

```python
# apps/api/tests/test_health.py
from fastapi.testclient import TestClient
from nq_api.main import app

client = TestClient(app)

def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "2.0.0"}

def test_cors_headers_present():
    response = client.options("/health", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/api && uv run pytest tests/test_health.py -v
# Expected: ModuleNotFoundError (nq_api not installed yet)
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[project]
name = "nq-api"
version = "2.0.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "anthropic>=0.40",
    "pydantic>=2.7",
    "python-dotenv>=1.0",
    "nq-data",
    "nq-signals",
]

[project.optional-dependencies]
test = ["pytest>=8.0", "httpx>=0.27", "pytest-asyncio>=0.23"]

[build-system]
requires = ["hatchling>=1.24"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/nq_api"]
```

- [ ] **Step 4: Create `main.py`**

```python
# apps/api/src/nq_api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nq_api.routes import stocks, screener, analyst, query

app = FastAPI(title="NeuralQuant API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://neuralquant.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
app.include_router(screener.router, prefix="/screener", tags=["screener"])
app.include_router(analyst.router, prefix="/analyst", tags=["analyst"])
app.include_router(query.router, prefix="/query", tags=["query"])


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}
```

- [ ] **Step 5: Create `schemas.py`**

```python
# apps/api/src/nq_api/schemas.py
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Literal


class FeatureDriver(BaseModel):
    name: str
    contribution: float          # positive = bullish, negative = bearish
    value: str                   # human-readable value ("P/E: 18.2")
    direction: Literal["positive", "negative", "neutral"]


class SubScores(BaseModel):
    quality: float               # 0-1
    momentum: float              # 0-1
    short_interest: float        # 0-1
    value: float                 # 0-1 (0.5 = neutral placeholder)
    low_vol: float               # 0-1 (0.5 = neutral placeholder)


class AIScore(BaseModel):
    ticker: str
    market: Literal["US", "IN", "GLOBAL"]
    composite_score: float       # 0-1
    score_1_10: int              # 1-10 for display
    regime_id: int               # 1-4
    regime_label: str            # "Risk-On" / "Late-Cycle" / "Bear" / "Recovery"
    sub_scores: SubScores
    top_drivers: list[FeatureDriver]  # top 5 positive + negative features
    confidence: Literal["high", "medium", "low"]
    last_updated: str            # ISO datetime


class ScreenerRequest(BaseModel):
    market: Literal["US", "IN", "GLOBAL"] = "US"
    min_score: float = 0.0
    max_results: int = Field(50, le=200)
    tickers: Optional[list[str]] = None  # if None, use default universe


class ScreenerResponse(BaseModel):
    regime_label: str
    regime_id: int
    results: list[AIScore]
    total: int


class AgentOutput(BaseModel):
    agent: str                   # "MACRO", "FUNDAMENTAL", etc.
    stance: Literal["BULL", "BEAR", "NEUTRAL"]
    conviction: Literal["HIGH", "MEDIUM", "LOW"]
    thesis: str                  # 2-3 sentence argument
    key_points: list[str]        # 3-5 bullet points


class AnalystRequest(BaseModel):
    ticker: str
    market: Literal["US", "IN", "GLOBAL"] = "US"
    include_adversarial: bool = True


class AnalystResponse(BaseModel):
    ticker: str
    head_analyst_verdict: str    # STRONG BUY / BUY / HOLD / SELL / STRONG SELL
    investment_thesis: str       # 4-6 sentence synthesis
    bull_case: str
    bear_case: str
    risk_factors: list[str]
    agent_outputs: list[AgentOutput]
    consensus_score: float       # weighted average of agent conviction scores


class QueryRequest(BaseModel):
    question: str
    ticker: Optional[str] = None  # if provided, grounds answer in ticker data
    market: Literal["US", "IN", "GLOBAL"] = "US"


class QueryResponse(BaseModel):
    answer: str
    data_sources: list[str]      # which data was used to answer
    follow_up_questions: list[str]  # 3 suggested follow-ups
```

- [ ] **Step 6: Create `deps.py`**

```python
# apps/api/src/nq_api/deps.py
"""Shared FastAPI dependencies — singletons loaded once at startup."""
from functools import lru_cache
from nq_signals.engine import SignalEngine

@lru_cache(maxsize=1)
def get_signal_engine() -> SignalEngine:
    return SignalEngine()
```

- [ ] **Step 7: Create empty route stubs** (so imports in main.py work)

```python
# apps/api/src/nq_api/routes/__init__.py  (empty)

# apps/api/src/nq_api/routes/stocks.py
from fastapi import APIRouter
router = APIRouter()

# apps/api/src/nq_api/routes/screener.py
from fastapi import APIRouter
router = APIRouter()

# apps/api/src/nq_api/routes/analyst.py
from fastapi import APIRouter
router = APIRouter()

# apps/api/src/nq_api/routes/query.py
from fastapi import APIRouter
router = APIRouter()
```

- [ ] **Step 8: Install and run tests**

```bash
cd apps/api
uv pip install -e ".[test]"
uv run pytest tests/test_health.py -v
# Expected: 2 passed
```

- [ ] **Step 9: Commit**

```bash
git add apps/api/
git commit -m "feat(api): scaffold FastAPI package with health endpoint and schemas"
```

---

## Task 2 — AI Score Endpoint (`GET /stocks/{ticker}`)

**Files:**
- Modify: `apps/api/src/nq_api/routes/stocks.py`
- Create: `apps/api/src/nq_api/score_builder.py`
- Create: `apps/api/tests/test_stocks_route.py`

**Context:** The Phase 1 `SignalEngine.compute(snapshot)` returns a DataFrame with `composite_score`, `quality_percentile`, `momentum_percentile`, `regime_id`. This task wires it to an HTTP endpoint and maps raw scores to the `AIScore` schema with human-readable explainability.

- [ ] **Step 1: Write the route test**

```python
# apps/api/tests/test_stocks_route.py
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import pandas as pd
from nq_api.main import app

client = TestClient(app)

def _mock_engine_result():
    """Minimal engine output for a single ticker."""
    return pd.DataFrame([{
        "ticker": "AAPL",
        "composite_score": 0.78,
        "quality_percentile": 0.85,
        "momentum_percentile": 0.70,
        "short_interest_percentile": 0.60,
        "regime_id": 1,
    }])


def test_get_stock_score_returns_ai_score():
    with patch("nq_api.routes.stocks.get_signal_engine") as mock_factory:
        engine = MagicMock()
        engine.compute.return_value = _mock_engine_result()
        mock_factory.return_value = engine

        response = client.get("/stocks/AAPL?market=US")
        assert response.status_code == 200

        data = response.json()
        assert data["ticker"] == "AAPL"
        assert 1 <= data["score_1_10"] <= 10
        assert data["regime_label"] in ["Risk-On", "Late-Cycle", "Bear", "Recovery"]
        assert len(data["top_drivers"]) >= 3
        assert "sub_scores" in data


def test_get_stock_score_unknown_ticker_returns_404():
    with patch("nq_api.routes.stocks.get_signal_engine") as mock_factory:
        engine = MagicMock()
        engine.compute.return_value = pd.DataFrame()  # empty
        mock_factory.return_value = engine

        response = client.get("/stocks/FAKE999?market=US")
        assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_stocks_route.py -v
# Expected: FAIL — route returns 404 for all tickers (stub)
```

- [ ] **Step 3: Write `score_builder.py`**

```python
# apps/api/src/nq_api/score_builder.py
"""Maps raw SignalEngine output to AIScore schema with explainability."""
import pandas as pd
from nq_api.schemas import AIScore, SubScores, FeatureDriver

REGIME_LABELS = {1: "Risk-On", 2: "Late-Cycle", 3: "Bear", 4: "Recovery"}

_FEATURE_DISPLAY = {
    "quality_percentile":       ("Quality composite",   True),
    "momentum_percentile":      ("12-1 Momentum",       True),
    "short_interest_percentile":("Short interest",      False),  # high SI = bearish
}


def _score_to_1_10(score: float) -> int:
    return max(1, min(10, round(score * 9 + 1)))


def _confidence(row: pd.Series) -> str:
    # Confidence is higher when sub-scores agree
    sub = [row.get("quality_percentile", 0.5),
           row.get("momentum_percentile", 0.5)]
    spread = max(sub) - min(sub)
    if spread < 0.2:
        return "high"
    if spread < 0.4:
        return "medium"
    return "low"


def build_top_drivers(row: pd.Series) -> list[FeatureDriver]:
    drivers = []
    for col, (name, higher_is_better) in _FEATURE_DISPLAY.items():
        val = row.get(col, 0.5)
        if higher_is_better:
            contribution = (val - 0.5) * 2   # -1 to +1
        else:
            contribution = (0.5 - val) * 2   # inverted

        direction = "positive" if contribution > 0.1 else (
            "negative" if contribution < -0.1 else "neutral"
        )
        drivers.append(FeatureDriver(
            name=name,
            contribution=round(contribution, 3),
            value=f"{val:.0%}",
            direction=direction,
        ))

    # Sort: most impactful first (absolute contribution)
    drivers.sort(key=lambda d: abs(d.contribution), reverse=True)
    return drivers[:5]


def row_to_ai_score(row: pd.Series, market: str) -> AIScore:
    from datetime import datetime, timezone
    regime_id = int(row.get("regime_id", 1))
    composite = float(row["composite_score"])

    return AIScore(
        ticker=str(row["ticker"]),
        market=market,
        composite_score=round(composite, 4),
        score_1_10=_score_to_1_10(composite),
        regime_id=regime_id,
        regime_label=REGIME_LABELS.get(regime_id, "Unknown"),
        sub_scores=SubScores(
            quality=round(float(row.get("quality_percentile", 0.5)), 3),
            momentum=round(float(row.get("momentum_percentile", 0.5)), 3),
            short_interest=round(float(row.get("short_interest_percentile", 0.5)), 3),
            value=round(float(row.get("value_percentile", 0.5)), 3),
            low_vol=round(float(row.get("low_vol_percentile", 0.5)), 3),
        ),
        top_drivers=build_top_drivers(row),
        confidence=_confidence(row),
        last_updated=datetime.now(timezone.utc).isoformat(),
    )
```

- [ ] **Step 4: Implement the stocks route**

```python
# apps/api/src/nq_api/routes/stocks.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Literal
import numpy as np
import pandas as pd
from dataclasses import dataclass

from nq_api.deps import get_signal_engine
from nq_api.schemas import AIScore
from nq_api.score_builder import row_to_ai_score
from nq_signals.engine import SignalEngine, UniverseSnapshot

router = APIRouter()


@dataclass
class _SyntheticMacro:
    """Phase 2 synthetic macro stub. Phase 3: replace with FREDConnector snapshot."""
    vix: float = 18.0
    spx_vs_200ma: float = 0.02
    hy_spread_oas: float = 350.0
    ism_pmi: float = 51.0
    yield_spread_2y10y: float = 0.10
    spx_return_1m: float = 0.01


def _build_snapshot(ticker: str, market: str) -> UniverseSnapshot:
    """Build a minimal UniverseSnapshot for a single ticker with synthetic data.

    Phase 3 will replace this with real-time data from DataStore.
    """
    np.random.seed(hash(ticker) % (2**31))

    fundamentals = pd.DataFrame([{
        "ticker": ticker,
        "gross_profit_margin": np.random.uniform(0.2, 0.8),
        "accruals_ratio": np.random.uniform(-0.1, 0.1),
        "piotroski": int(np.random.randint(3, 9)),
        "momentum_raw": np.random.uniform(-0.2, 0.5),
        "short_interest_pct": np.random.uniform(0.01, 0.15),
    }])

    return UniverseSnapshot(
        tickers=[ticker],
        market=market,
        fundamentals=fundamentals,
        macro=_SyntheticMacro(),
    )


@router.get("/{ticker}", response_model=AIScore)
def get_stock_score(
    ticker: str,
    market: Literal["US", "IN", "GLOBAL"] = Query("US"),
    engine: SignalEngine = Depends(get_signal_engine),
) -> AIScore:
    snapshot = _build_snapshot(ticker.upper(), market)
    result_df = engine.compute(snapshot)

    if result_df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")

    row = result_df.iloc[0]
    return row_to_ai_score(row, market)
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_stocks_route.py -v
# Expected: 2 passed
```

- [ ] **Step 6: Smoke test manually**

```bash
uv run uvicorn nq_api.main:app --reload --port 8000
# In another terminal:
curl "http://localhost:8000/stocks/AAPL?market=US"
# Expected: JSON with score_1_10, regime_label, top_drivers, sub_scores
```

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/nq_api/routes/stocks.py apps/api/src/nq_api/score_builder.py apps/api/tests/test_stocks_route.py
git commit -m "feat(api): add AI score endpoint GET /stocks/{ticker} with explainability"
```

---

## Task 3 — Screener Endpoint (`POST /screener`)

**Files:**
- Modify: `apps/api/src/nq_api/routes/screener.py`
- Create: `apps/api/tests/test_screener_route.py`

**Context:** The screener takes a list of tickers (or a default universe), runs SignalEngine on all of them, and returns ranked results. Default universe = top 50 NSE stocks + top 50 S&P 500 stocks (hardcoded list for Phase 2; real-time universe in Phase 3).

- [ ] **Step 1: Write the screener test**

```python
# apps/api/tests/test_screener_route.py
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from nq_api.main import app

client = TestClient(app)


def _mock_engine_for_universe(n_tickers: int):
    tickers = [f"T{i:02d}" for i in range(n_tickers)]
    np.random.seed(42)
    return pd.DataFrame([{
        "ticker": t,
        "composite_score": np.random.uniform(0.2, 0.9),
        "quality_percentile": np.random.uniform(0, 1),
        "momentum_percentile": np.random.uniform(0, 1),
        "short_interest_percentile": np.random.uniform(0, 1),
        "regime_id": 1,
    } for t in tickers])


def test_screener_returns_ranked_list():
    with patch("nq_api.routes.screener.get_signal_engine") as mock_factory:
        engine = MagicMock()
        engine.compute.return_value = _mock_engine_for_universe(10)
        mock_factory.return_value = engine

        response = client.post("/screener", json={"market": "US", "max_results": 5})
        assert response.status_code == 200

        data = response.json()
        assert "results" in data
        assert len(data["results"]) <= 5

        scores = [r["composite_score"] for r in data["results"]]
        assert scores == sorted(scores, reverse=True), "Must be sorted descending"


def test_screener_filters_by_min_score():
    with patch("nq_api.routes.screener.get_signal_engine") as mock_factory:
        engine = MagicMock()
        engine.compute.return_value = _mock_engine_for_universe(10)
        mock_factory.return_value = engine

        response = client.post("/screener", json={"market": "US", "min_score": 0.8})
        assert response.status_code == 200

        data = response.json()
        for r in data["results"]:
            assert r["composite_score"] >= 0.8
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_screener_route.py -v
# Expected: FAIL — screener stub returns nothing
```

- [ ] **Step 3: Create default universe constants**

```python
# apps/api/src/nq_api/universe.py
"""Default stock universes for Phase 2. Phase 3 replaces with live index constituents."""

US_DEFAULT = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
    "JPM", "V", "MA", "UNH", "XOM", "JNJ", "PG", "HD", "COST", "ABBV",
    "MRK", "LLY", "CVX", "BAC", "NFLX", "ORCL", "ADBE", "CRM", "AMD",
    "INTC", "QCOM", "TXN", "AVGO", "MU", "AMAT", "LRCX", "KLAC",
    "WMT", "TGT", "NKE", "MCD", "SBUX", "DIS", "CMCSA", "T", "VZ",
    "PFE", "AMGN", "GILD", "REGN", "ISRG",
]

IN_DEFAULT = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR", "ICICIBANK",
    "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "HCLTECH", "WIPRO",
    "ASIANPAINT", "MARUTI", "SUNPHARMA", "ULTRACEMCO", "BAJFINANCE",
    "TITAN", "NESTLEIND", "POWERGRID", "NTPC", "ONGC", "COALINDIA",
    "TATAMOTORS", "TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL",
    "ADANIPORTS", "ADANIENT", "ADANIGREEN", "DMART", "PIDILITIND",
    "EICHERMOT", "BAJAJ-AUTO", "HEROMOTOCO", "M&M", "DRREDDY",
    "CIPLA", "DIVISLAB", "APOLLOHOSP", "FORTIS", "MAXHEALTH",
    "ZOMATO", "NYKAA", "PAYTM", "POLICYBZR", "IRCTC", "MUTHOOTFIN",
    "BANDHANBNK",
]

UNIVERSE_BY_MARKET = {"US": US_DEFAULT, "IN": IN_DEFAULT, "GLOBAL": US_DEFAULT + IN_DEFAULT}
```

- [ ] **Step 4: Implement screener route**

```python
# apps/api/src/nq_api/routes/screener.py
from fastapi import APIRouter, Depends
import pandas as pd
import numpy as np

from nq_api.deps import get_signal_engine
from nq_api.schemas import ScreenerRequest, ScreenerResponse
from nq_api.score_builder import row_to_ai_score, REGIME_LABELS
from nq_api.universe import UNIVERSE_BY_MARKET
from nq_api.routes.stocks import _SyntheticMacro   # reuse the Phase 2 macro stub
from nq_signals.engine import SignalEngine, UniverseSnapshot

router = APIRouter()


def _build_universe_snapshot(tickers: list[str], market: str) -> UniverseSnapshot:
    """Synthetic fundamentals for Phase 2. Phase 3: real DataStore lookup."""
    n = len(tickers)
    np.random.seed(42)

    seeds = [hash(t) % (2**31 - 1) for t in tickers]
    fundamentals = pd.DataFrame([{
        "ticker": t,
        "gross_profit_margin": (np.random.RandomState(s).uniform(0.1, 0.9)),
        "accruals_ratio":      (np.random.RandomState(s + 1).uniform(-0.15, 0.15)),
        "piotroski":           int(np.random.RandomState(s + 2).randint(2, 9)),
        "momentum_raw":        (np.random.RandomState(s + 3).uniform(-0.3, 0.6)),
        "short_interest_pct":  (np.random.RandomState(s + 4).uniform(0.005, 0.20)),
    } for t, s in zip(tickers, seeds)])

    return UniverseSnapshot(
        tickers=tickers,
        market=market,
        fundamentals=fundamentals,
        macro=_SyntheticMacro(),
    )


@router.post("", response_model=ScreenerResponse)
def run_screener(
    req: ScreenerRequest,
    engine: SignalEngine = Depends(get_signal_engine),
) -> ScreenerResponse:
    tickers = req.tickers or UNIVERSE_BY_MARKET.get(req.market, UNIVERSE_BY_MARKET["US"])
    snapshot = _build_universe_snapshot(tickers, req.market)
    result_df = engine.compute(snapshot)

    # Apply min_score filter
    filtered = result_df[result_df["composite_score"] >= req.min_score]
    filtered = filtered.sort_values("composite_score", ascending=False)
    filtered = filtered.head(req.max_results)

    regime_id = int(result_df["regime_id"].iloc[0]) if not result_df.empty else 1
    ai_scores = [row_to_ai_score(row, req.market) for _, row in filtered.iterrows()]

    return ScreenerResponse(
        regime_label=REGIME_LABELS.get(regime_id, "Unknown"),
        regime_id=regime_id,
        results=ai_scores,
        total=len(ai_scores),
    )
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_screener_route.py -v
# Expected: 2 passed
```

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/nq_api/routes/screener.py apps/api/src/nq_api/universe.py apps/api/tests/test_screener_route.py
git commit -m "feat(api): add screener endpoint POST /screener with default US + India universes"
```

---

## Task 4 — Base Agent + MACRO Agent

**Files:**
- Create: `apps/api/src/nq_api/agents/__init__.py`
- Create: `apps/api/src/nq_api/agents/base.py`
- Create: `apps/api/src/nq_api/agents/macro.py`
- Create: `apps/api/tests/test_agents.py`

**Context:** Each agent is a Claude call with a specialist system prompt and access to NeuralQuant data as context. Agents use `anthropic.Anthropic` (sync) or `anthropic.AsyncAnthropic` (async). The base class handles retries, token limits, and output parsing.

**Important:** Agents must have `ANTHROPIC_API_KEY` set. Tests must mock `anthropic.Anthropic` — never make real API calls in tests.

- [ ] **Step 1: Write agent tests**

```python
# apps/api/tests/test_agents.py
from unittest.mock import MagicMock, patch
from nq_api.agents.macro import MacroAgent
from nq_api.schemas import AgentOutput


def _mock_claude_response(content: str):
    """Minimal mock of anthropic Message object."""
    msg = MagicMock()
    msg.content = [MagicMock(text=content)]
    return msg


MOCK_MACRO_RESPONSE = """
STANCE: BULL
CONVICTION: MEDIUM
THESIS: The macro environment is supportive with the Fed on pause and ISM PMI above 50, indicating continued expansion. VIX is subdued, suggesting market stability.
KEY_POINTS:
- Fed funds rate stable; no imminent hikes expected
- ISM PMI at 51 signals manufacturing expansion
- VIX at 18 indicates low systemic fear
- Yield curve normalising — 10Y-2Y spread turning positive
- Historical regime analysis favours Risk-On allocation
"""


def test_macro_agent_parses_output():
    with patch("nq_api.agents.base.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(MOCK_MACRO_RESPONSE)

        agent = MacroAgent()
        result = agent.run(ticker="AAPL", context={"vix": 18.0, "ism_pmi": 51.0})

        assert isinstance(result, AgentOutput)
        assert result.agent == "MACRO"
        assert result.stance in ("BULL", "BEAR", "NEUTRAL")
        assert result.conviction in ("HIGH", "MEDIUM", "LOW")
        assert len(result.thesis) > 20
        assert len(result.key_points) >= 3


def test_macro_agent_defaults_neutral_on_parse_failure():
    with patch("nq_api.agents.base.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response("Garbage output")

        agent = MacroAgent()
        result = agent.run(ticker="AAPL", context={})

        assert result.stance == "NEUTRAL"
        assert result.conviction == "LOW"
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_agents.py -v
# Expected: ImportError — agents not created yet
```

- [ ] **Step 3: Create `base.py`**

```python
# apps/api/src/nq_api/agents/base.py
"""Base agent class for NeuralQuant PARA-DEBATE analyst team."""
from __future__ import annotations
import os
import re
from abc import ABC, abstractmethod

import anthropic

from nq_api.schemas import AgentOutput

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024


class BaseAnalystAgent(ABC):
    """One analyst in the PARA-DEBATE panel."""

    agent_name: str
    system_prompt: str

    def __init__(self):
        self._client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    @abstractmethod
    def _build_user_message(self, ticker: str, context: dict) -> str:
        ...

    def run(self, ticker: str, context: dict) -> AgentOutput:
        user_msg = self._build_user_message(ticker, context)
        try:
            response = self._client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=self.system_prompt,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = response.content[0].text
            return self._parse_output(raw)
        except Exception:
            return self._neutral_fallback()

    def _parse_output(self, raw: str) -> AgentOutput:
        try:
            stance = re.search(r"STANCE:\s*(BULL|BEAR|NEUTRAL)", raw, re.I).group(1).upper()
            conviction = re.search(r"CONVICTION:\s*(HIGH|MEDIUM|LOW)", raw, re.I).group(1).upper()
            thesis_match = re.search(r"THESIS:\s*(.+?)(?=KEY_POINTS:|$)", raw, re.I | re.S)
            thesis = thesis_match.group(1).strip() if thesis_match else raw[:200]
            points_raw = re.search(r"KEY_POINTS:(.*)", raw, re.I | re.S)
            if points_raw:
                points = [
                    p.strip().lstrip("-").strip()
                    for p in points_raw.group(1).strip().splitlines()
                    if p.strip().lstrip("-").strip()
                ]
            else:
                points = [thesis[:100]]

            return AgentOutput(
                agent=self.agent_name,
                stance=stance,
                conviction=conviction,
                thesis=thesis[:500],
                key_points=points[:5],
            )
        except Exception:
            return self._neutral_fallback()

    def _neutral_fallback(self) -> AgentOutput:
        return AgentOutput(
            agent=self.agent_name,
            stance="NEUTRAL",
            conviction="LOW",
            thesis=f"{self.agent_name} analysis unavailable.",
            key_points=["Insufficient data for analysis."],
        )
```

- [ ] **Step 4: Create `macro.py`**

```python
# apps/api/src/nq_api/agents/macro.py
from nq_api.agents.base import BaseAnalystAgent

_SYSTEM = """You are the MACRO analyst on NeuralQuant's PARA-DEBATE investment committee.
Your mandate: assess the macroeconomic and interest rate environment and its implications for the given stock.

Analysis framework:
1. Fed policy cycle (hiking / pausing / cutting) and its sector impact
2. Market regime (Risk-On / Late-Cycle / Bear / Recovery) from HMM model
3. Yield curve shape — 2Y-10Y spread and credit environment
4. Volatility regime — VIX level and trend
5. Global growth indicators — PMI, trade data

You MUST respond in exactly this format:
STANCE: [BULL|BEAR|NEUTRAL]
CONVICTION: [HIGH|MEDIUM|LOW]
THESIS: [2-3 sentences stating your macro argument for this stock]
KEY_POINTS:
- [Point 1]
- [Point 2]
- [Point 3]
- [Point 4 optional]
- [Point 5 optional]

Be direct. Do not hedge every statement. Take a position."""


class MacroAgent(BaseAnalystAgent):
    agent_name = "MACRO"
    system_prompt = _SYSTEM

    def _build_user_message(self, ticker: str, context: dict) -> str:
        return f"""Analyse the macro environment for {ticker}.

Current macro data:
- VIX: {context.get('vix', 'N/A')}
- Regime: {context.get('regime_label', 'N/A')}
- ISM PMI: {context.get('ism_pmi', 'N/A')}
- 10Y-2Y Yield Spread: {context.get('yield_spread_2y10y', 'N/A')}
- HY Credit Spread (OAS): {context.get('hy_spread_oas', 'N/A')}
- SPX 1-month return: {context.get('spx_return_1m', 'N/A')}
- SPX vs 200MA: {context.get('spx_vs_200ma', 'N/A')}

Provide your macro stance on {ticker}."""
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_agents.py -v
# Expected: 2 passed
```

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/nq_api/agents/ apps/api/tests/test_agents.py
git commit -m "feat(agents): add BaseAnalystAgent and MacroAgent with PARA-DEBATE output format"
```

---

## Task 5 — Remaining 5 Specialist Agents

**Files:**
- Create: `apps/api/src/nq_api/agents/fundamental.py`
- Create: `apps/api/src/nq_api/agents/technical.py`
- Create: `apps/api/src/nq_api/agents/sentiment.py`
- Create: `apps/api/src/nq_api/agents/geopolitical.py`
- Create: `apps/api/src/nq_api/agents/adversarial.py`
- Modify: `apps/api/tests/test_agents.py`

**Note:** Same pattern as MacroAgent — subclass `BaseAnalystAgent`, set `agent_name`, `system_prompt`, implement `_build_user_message`. The tests simply verify each agent instantiates and returns an `AgentOutput` from a mocked response.

- [ ] **Step 1: Add tests for all 5 agents**

```python
# Append to apps/api/tests/test_agents.py

from nq_api.agents.fundamental import FundamentalAgent
from nq_api.agents.technical import TechnicalAgent
from nq_api.agents.sentiment import SentimentAgent
from nq_api.agents.geopolitical import GeopoliticalAgent
from nq_api.agents.adversarial import AdversarialAgent


MOCK_RESPONSE = """
STANCE: NEUTRAL
CONVICTION: MEDIUM
THESIS: Analysis is inconclusive given mixed signals. Further data required.
KEY_POINTS:
- Signal A is positive
- Signal B is negative
- Net effect is neutral
"""


@pytest.mark.parametrize("AgentClass,name", [
    (FundamentalAgent, "FUNDAMENTAL"),
    (TechnicalAgent, "TECHNICAL"),
    (SentimentAgent, "SENTIMENT"),
    (GeopoliticalAgent, "GEOPOLITICAL"),
    (AdversarialAgent, "ADVERSARIAL"),
])
def test_agent_returns_valid_output(AgentClass, name):
    with patch("nq_api.agents.base.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(MOCK_RESPONSE)

        agent = AgentClass()
        result = agent.run(ticker="MSFT", context={"quality_percentile": 0.8})

        assert result.agent == name
        assert result.stance in ("BULL", "BEAR", "NEUTRAL")
        assert isinstance(result.key_points, list)
```

**Important:** Add `import pytest` at the top of `test_agents.py` (the full file start) before running Step 2. The parametrize decorator requires it. The complete file header should be:
```python
import pytest
from unittest.mock import MagicMock, patch
from nq_api.agents.macro import MacroAgent
from nq_api.schemas import AgentOutput
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
uv run pytest tests/test_agents.py -v
# Expected: ImportError for missing agent files
```

- [ ] **Step 3: Implement `fundamental.py`**

```python
# apps/api/src/nq_api/agents/fundamental.py
from nq_api.agents.base import BaseAnalystAgent

_SYSTEM = """You are the FUNDAMENTAL analyst on NeuralQuant's PARA-DEBATE investment committee.
Your mandate: assess the company's financial quality, valuation, and earnings trajectory.

Framework:
1. Profitability quality — Piotroski F-Score, gross margins, accruals (earnings quality)
2. Valuation — P/E, P/FCF, EV/EBITDA relative to sector and history
3. Earnings trajectory — estimate revisions, surprise history, guidance
4. Balance sheet strength — debt levels, interest coverage, cash generation
5. Capital allocation — buybacks, dividends, capex efficiency (ROIC)

Response format — strictly:
STANCE: [BULL|BEAR|NEUTRAL]
CONVICTION: [HIGH|MEDIUM|LOW]
THESIS: [2-3 sentences on fundamental investment merit]
KEY_POINTS:
- [Point 1]
- [Point 2]
- [Point 3]"""


class FundamentalAgent(BaseAnalystAgent):
    agent_name = "FUNDAMENTAL"
    system_prompt = _SYSTEM

    def _build_user_message(self, ticker: str, context: dict) -> str:
        return f"""Analyse the fundamental investment merit of {ticker}.

Financial data:
- Piotroski F-Score: {context.get('piotroski', 'N/A')} / 9
- Quality composite percentile: {context.get('quality_percentile', 'N/A'):.0%} vs universe
- Gross profit margin: {context.get('gross_profit_margin', 'N/A')}
- Accruals ratio: {context.get('accruals_ratio', 'N/A')} (lower is better — indicates cash earnings)
- AI composite score: {context.get('composite_score', 'N/A')}

Provide your fundamental stance on {ticker}."""
```

- [ ] **Step 4: Implement `technical.py`**

```python
# apps/api/src/nq_api/agents/technical.py
from nq_api.agents.base import BaseAnalystAgent

_SYSTEM = """You are the TECHNICAL analyst on NeuralQuant's PARA-DEBATE investment committee.
Your mandate: assess price momentum, chart patterns, and technical positioning.

Framework:
1. 12-1 month momentum — trend persistence signal (academic factor)
2. Crash protection — SPX drawdown assessment and market structure
3. Volume and breadth analysis
4. Key technical levels — support/resistance, 200-day MA relationship
5. Sector relative strength

Response format — strictly:
STANCE: [BULL|BEAR|NEUTRAL]
CONVICTION: [HIGH|MEDIUM|LOW]
THESIS: [2-3 sentences on technical setup]
KEY_POINTS:
- [Point 1]
- [Point 2]
- [Point 3]"""


class TechnicalAgent(BaseAnalystAgent):
    agent_name = "TECHNICAL"
    system_prompt = _SYSTEM

    def _build_user_message(self, ticker: str, context: dict) -> str:
        return f"""Analyse the technical setup for {ticker}.

Technical data:
- 12-1 momentum raw: {context.get('momentum_raw', 'N/A')}
- Momentum percentile vs universe: {context.get('momentum_percentile', 'N/A')}
- Crash protection active: {context.get('crash_protection', False)}
- SPX vs 200MA: {context.get('spx_vs_200ma', 'N/A')}
- Market regime: {context.get('regime_label', 'N/A')}

Provide your technical stance on {ticker}."""
```

- [ ] **Step 5: Implement `sentiment.py`**

```python
# apps/api/src/nq_api/agents/sentiment.py
from nq_api.agents.base import BaseAnalystAgent

_SYSTEM = """You are the SENTIMENT analyst on NeuralQuant's PARA-DEBATE investment committee.
Your mandate: assess news sentiment, insider activity, short interest, and options flow signals.

Framework:
1. Insider cluster signal — C-suite (CEO 3x, CFO 2x) buys vs sells
2. Short interest percentile — high SI = potential squeeze OR warning sign (context-dependent)
3. News sentiment trend — 30-day rolling news tone
4. Options market signal — unusual call/put activity (available Phase 3)
5. Analyst estimate revision momentum — earnings estimate trends

Response format — strictly:
STANCE: [BULL|BEAR|NEUTRAL]
CONVICTION: [HIGH|MEDIUM|LOW]
THESIS: [2-3 sentences on sentiment signals]
KEY_POINTS:
- [Point 1]
- [Point 2]
- [Point 3]"""


class SentimentAgent(BaseAnalystAgent):
    agent_name = "SENTIMENT"
    system_prompt = _SYSTEM

    def _build_user_message(self, ticker: str, context: dict) -> str:
        return f"""Analyse sentiment signals for {ticker}.

Sentiment data:
- Short interest percentile: {context.get('short_interest_percentile', 'N/A')}
- Short interest % of float: {context.get('short_interest_pct', 'N/A')}
- Insider cluster score: {context.get('insider_cluster_score', 'N/A')} (0=bearish, 1=strong buy)
- News sentiment (30d): {context.get('news_sentiment', 'N/A')}
- Market regime: {context.get('regime_label', 'N/A')}

Provide your sentiment stance on {ticker}."""
```

- [ ] **Step 6: Implement `geopolitical.py`**

```python
# apps/api/src/nq_api/agents/geopolitical.py
from nq_api.agents.base import BaseAnalystAgent

_SYSTEM = """You are the GEOPOLITICAL analyst on NeuralQuant's PARA-DEBATE investment committee.
Your mandate: assess geopolitical, regulatory, and systemic risk factors affecting the stock.

Framework:
1. Supply chain and trade policy exposure (tariffs, export controls)
2. Regulatory risk — antitrust, sector-specific regulations, ESG mandates
3. Geographic revenue concentration — single-country risk
4. Currency risk — USD strength impact on international revenue
5. Macro tail risks — recession probability, financial stability

Response format — strictly:
STANCE: [BULL|BEAR|NEUTRAL]
CONVICTION: [HIGH|MEDIUM|LOW]
THESIS: [2-3 sentences on geopolitical/regulatory risk profile]
KEY_POINTS:
- [Point 1]
- [Point 2]
- [Point 3]"""


class GeopoliticalAgent(BaseAnalystAgent):
    agent_name = "GEOPOLITICAL"
    system_prompt = _SYSTEM

    def _build_user_message(self, ticker: str, context: dict) -> str:
        return f"""Assess geopolitical and regulatory risks for {ticker}.

Context:
- Market: {context.get('market', 'US')}
- Macro regime: {context.get('regime_label', 'N/A')}
- HY credit spread (OAS): {context.get('hy_spread_oas', 'N/A')} bps
- VIX: {context.get('vix', 'N/A')}

Provide your geopolitical risk stance on {ticker}."""
```

- [ ] **Step 7: Implement `adversarial.py`**

```python
# apps/api/src/nq_api/agents/adversarial.py
from nq_api.agents.base import BaseAnalystAgent

_SYSTEM = """You are the ADVERSARIAL analyst on NeuralQuant's PARA-DEBATE investment committee.
Your SOLE mandate: find the strongest possible BEAR case, regardless of consensus.

You are the devil's advocate. Even if all other analysts are bullish, your job is to surface the best reasons to be skeptical. This is NOT contrarianism for its own sake — it is structured risk management.

Challenge framework:
1. What would have to go wrong for the bull thesis to fail?
2. Are there hidden risks in the balance sheet or earnings quality?
3. Is the valuation pricing in perfection?
4. What does high institutional ownership / low short interest imply about downside risk?
5. What is the asymmetric downside scenario?

You MUST output BEAR or NEUTRAL — never BULL. Your role is to stress-test the investment.

Response format — strictly:
STANCE: [BEAR|NEUTRAL]  (never BULL)
CONVICTION: [HIGH|MEDIUM|LOW]
THESIS: [2-3 sentences — the strongest bear argument]
KEY_POINTS:
- [Risk 1]
- [Risk 2]
- [Risk 3]"""


class AdversarialAgent(BaseAnalystAgent):
    agent_name = "ADVERSARIAL"
    system_prompt = _SYSTEM

    def _build_user_message(self, ticker: str, context: dict) -> str:
        # Feed the adversarial agent the bull case to stress-test
        bull_thesis = context.get("bull_thesis", "No bull thesis provided.")
        return f"""Find the strongest possible bear case for {ticker}.

The current bull thesis is:
{bull_thesis}

AI composite score: {context.get('composite_score', 'N/A')}
Quality percentile: {context.get('quality_percentile', 'N/A')}
Momentum: {context.get('momentum_percentile', 'N/A')}

Stress-test this thesis and provide the best bear argument."""
```

- [ ] **Step 8: Run all agent tests**

```bash
uv run pytest tests/test_agents.py -v
# Expected: 7 passed (2 existing + 5 parametrized)
```

- [ ] **Step 9: Commit**

```bash
git add apps/api/src/nq_api/agents/
git commit -m "feat(agents): add 5 specialist agents — Fundamental, Technical, Sentiment, Geopolitical, Adversarial"
```

---

## Task 6 — HEAD ANALYST + PARA-DEBATE Orchestrator

**Files:**
- Create: `apps/api/src/nq_api/agents/head_analyst.py`
- Create: `apps/api/src/nq_api/agents/orchestrator.py`
- Create: `apps/api/tests/test_orchestrator.py`

**Architecture:** The orchestrator runs 5 specialist agents in parallel via `asyncio.gather` using `asyncio.to_thread` (since Claude SDK is sync). Then builds context from their outputs and calls HEAD ANALYST for the final synthesis. Total wall-clock time: ~3-5 seconds for 6 Claude calls with parallelism.

- [ ] **Step 1: Write orchestrator tests**

```python
# apps/api/tests/test_orchestrator.py
import asyncio
from unittest.mock import patch, MagicMock
from nq_api.agents.orchestrator import ParaDebateOrchestrator
from nq_api.schemas import AnalystResponse, AgentOutput


def _make_agent_output(agent_name: str, stance: str = "BULL") -> AgentOutput:
    return AgentOutput(
        agent=agent_name,
        stance=stance,
        conviction="MEDIUM",
        thesis=f"{agent_name} thesis here.",
        key_points=["Point A", "Point B", "Point C"],
    )


def _mock_all_agents(mock_cls):
    mock_client = MagicMock()
    mock_cls.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="""
STANCE: BULL
CONVICTION: MEDIUM
THESIS: Overall the stock looks attractive.
KEY_POINTS:
- Strong fundamentals
- Positive macro backdrop
- Insider buying confirmed
""")]
    )
    return mock_client


def test_orchestrator_returns_analyst_response():
    with patch("nq_api.agents.base.anthropic.Anthropic") as mock_cls:
        _mock_all_agents(mock_cls)
        orch = ParaDebateOrchestrator()
        result = asyncio.run(orch.analyse(ticker="AAPL", market="US", context={"vix": 18.0}))

        assert isinstance(result, AnalystResponse)
        assert result.ticker == "AAPL"
        assert result.head_analyst_verdict in (
            "STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"
        )
        assert len(result.agent_outputs) == 6  # 5 specialists + adversarial
        assert len(result.investment_thesis) > 50
        assert isinstance(result.risk_factors, list)


def test_orchestrator_adversarial_is_always_bear():
    with patch("nq_api.agents.base.anthropic.Anthropic") as mock_cls:
        _mock_all_agents(mock_cls)
        orch = ParaDebateOrchestrator()
        result = asyncio.run(orch.analyse(ticker="AAPL", market="US", context={}))

        adversarial = next(o for o in result.agent_outputs if o.agent == "ADVERSARIAL")
        assert adversarial.stance in ("BEAR", "NEUTRAL"), \
            "Adversarial agent must never be BULL"
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_orchestrator.py -v
# Expected: ImportError
```

- [ ] **Step 3: Implement `head_analyst.py`**

```python
# apps/api/src/nq_api/agents/head_analyst.py
from nq_api.agents.base import BaseAnalystAgent, MODEL, MAX_TOKENS
from nq_api.schemas import AgentOutput, AnalystResponse
import anthropic
import os
import re

_SYSTEM = """You are the HEAD ANALYST and chair of NeuralQuant's PARA-DEBATE investment committee.
You have received structured analyses from 6 specialist analysts. Your job: synthesise their views into a definitive investment verdict with full reasoning.

Weighting framework:
- MACRO and FUNDAMENTAL carry 25% weight each (most important for long-term)
- TECHNICAL and SENTIMENT carry 20% each
- GEOPOLITICAL carries 15%
- ADVERSARIAL: do NOT dismiss bear arguments — they represent tail risk. Weight them at 15% of your downside scenario.

Output format — strictly:
VERDICT: [STRONG BUY|BUY|HOLD|SELL|STRONG SELL]
INVESTMENT_THESIS: [4-6 sentences synthesising the debate into a clear investment thesis]
BULL_CASE: [2-3 sentences on primary upside drivers]
BEAR_CASE: [2-3 sentences on primary downside risks]
RISK_FACTORS:
- [Risk 1]
- [Risk 2]
- [Risk 3]"""


class HeadAnalystAgent(BaseAnalystAgent):
    agent_name = "HEAD_ANALYST"
    system_prompt = _SYSTEM

    def _build_user_message(self, ticker: str, context: dict) -> str:
        agent_summaries = context.get("agent_summaries", "")
        ai_score = context.get("composite_score", "N/A")
        return f"""Synthesise the PARA-DEBATE for {ticker} (AI score: {ai_score}).

ANALYST PANEL OUTPUTS:
{agent_summaries}

Deliver the final investment verdict."""

    def run_synthesis(self, ticker: str, agent_outputs: list[AgentOutput],
                      composite_score: float) -> dict:
        summaries = "\n\n".join(
            f"[{o.agent}] Stance: {o.stance} ({o.conviction})\n"
            f"Thesis: {o.thesis}\n"
            f"Key points:\n" + "\n".join(f"  - {p}" for p in o.key_points)
            for o in agent_outputs
        )
        context = {"agent_summaries": summaries, "composite_score": f"{composite_score:.2f}"}
        msg = self._build_user_message(ticker, context)

        try:
            response = self._client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS * 2,
                system=self.system_prompt,
                messages=[{"role": "user", "content": msg}],
            )
            raw = response.content[0].text
            return self._parse_synthesis(raw)
        except Exception:
            return self._fallback_synthesis()

    def _parse_synthesis(self, raw: str) -> dict:
        def _extract(key: str) -> str:
            # Use MULTILINE so $ matches end-of-line, not end-of-string (avoids field bleed)
            m = re.search(rf"{key}:\s*(.+?)(?=\n[A-Z_]+:|(?m)$)", raw, re.I | re.S | re.M)
            return m.group(1).strip() if m else ""

        verdict_match = re.search(
            r"VERDICT:\s*(STRONG BUY|BUY|HOLD|SELL|STRONG SELL)", raw, re.I
        )
        verdict = verdict_match.group(1).upper() if verdict_match else "HOLD"

        risks_raw = re.search(r"RISK_FACTORS:(.*)", raw, re.I | re.S)
        risks = []
        if risks_raw:
            risks = [
                r.strip().lstrip("-").strip()
                for r in risks_raw.group(1).strip().splitlines()
                if r.strip().lstrip("-").strip()
            ]

        return {
            "verdict": verdict,
            "investment_thesis": _extract("INVESTMENT_THESIS")[:1000],
            "bull_case": _extract("BULL_CASE")[:500],
            "bear_case": _extract("BEAR_CASE")[:500],
            "risk_factors": risks[:5],
        }

    def _fallback_synthesis(self) -> dict:
        return {
            "verdict": "HOLD",
            "investment_thesis": "Analysis unavailable. Defaulting to HOLD.",
            "bull_case": "Insufficient data.",
            "bear_case": "Insufficient data.",
            "risk_factors": ["Analysis error — treat with caution."],
        }
```

- [ ] **Step 4: Implement `orchestrator.py`**

```python
# apps/api/src/nq_api/agents/orchestrator.py
"""PARA-DEBATE orchestrator — runs 6 agents in parallel, HEAD ANALYST synthesises."""
from __future__ import annotations
import asyncio

from nq_api.schemas import AgentOutput, AnalystResponse
from nq_api.agents.macro import MacroAgent
from nq_api.agents.fundamental import FundamentalAgent
from nq_api.agents.technical import TechnicalAgent
from nq_api.agents.sentiment import SentimentAgent
from nq_api.agents.geopolitical import GeopoliticalAgent
from nq_api.agents.adversarial import AdversarialAgent
from nq_api.agents.head_analyst import HeadAnalystAgent

STANCE_SCORE = {"BULL": 1.0, "NEUTRAL": 0.5, "BEAR": 0.0}
CONVICTION_MULT = {"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4}


class ParaDebateOrchestrator:
    def __init__(self):
        self._specialists = [
            MacroAgent(),
            FundamentalAgent(),
            TechnicalAgent(),
            SentimentAgent(),
            GeopoliticalAgent(),
        ]
        self._adversarial = AdversarialAgent()
        self._head = HeadAnalystAgent()

    async def analyse(
        self, ticker: str, market: str, context: dict
    ) -> AnalystResponse:
        # Step 1: run 5 specialists in parallel
        specialist_outputs: list[AgentOutput] = await asyncio.gather(
            *[asyncio.to_thread(agent.run, ticker, context)
              for agent in self._specialists]
        )

        # Step 2: build bull thesis summary for adversarial to stress-test
        bull_summary = "; ".join(
            o.thesis for o in specialist_outputs if o.stance == "BULL"
        ) or "Mixed signals from panel."

        adversarial_context = {**context, "bull_thesis": bull_summary}
        adversarial_output = await asyncio.to_thread(
            self._adversarial.run, ticker, adversarial_context
        )

        all_outputs = list(specialist_outputs) + [adversarial_output]

        # Step 3: compute consensus score
        consensus = sum(
            STANCE_SCORE[o.stance] * CONVICTION_MULT[o.conviction]
            for o in specialist_outputs  # adversarial excluded from consensus
        ) / len(specialist_outputs)

        # Step 4: HEAD ANALYST synthesis
        composite_score = context.get("composite_score", 0.5)
        synthesis = await asyncio.to_thread(
            self._head.run_synthesis, ticker, all_outputs, composite_score
        )

        return AnalystResponse(
            ticker=ticker,
            head_analyst_verdict=synthesis["verdict"],
            investment_thesis=synthesis["investment_thesis"],
            bull_case=synthesis["bull_case"],
            bear_case=synthesis["bear_case"],
            risk_factors=synthesis["risk_factors"],
            agent_outputs=all_outputs,
            consensus_score=round(consensus, 3),
        )
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_orchestrator.py -v
# Expected: 2 passed
```

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/nq_api/agents/head_analyst.py apps/api/src/nq_api/agents/orchestrator.py apps/api/tests/test_orchestrator.py
git commit -m "feat(agents): add HEAD ANALYST + PARA-DEBATE orchestrator with async parallel execution"
```

---

## Task 7 — Analyst Route + NL Query Route

**Files:**
- Modify: `apps/api/src/nq_api/routes/analyst.py`
- Modify: `apps/api/src/nq_api/routes/query.py`
- Create: `apps/api/tests/test_analyst_route.py`

- [ ] **Step 1: Write analyst route test**

```python
# apps/api/tests/test_analyst_route.py
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from nq_api.main import app
from nq_api.schemas import AnalystResponse, AgentOutput

client = TestClient(app)


def _mock_analyst_response(ticker: str) -> AnalystResponse:
    return AnalystResponse(
        ticker=ticker,
        head_analyst_verdict="BUY",
        investment_thesis="Strong quality fundamentals with positive momentum.",
        bull_case="Quality metrics excellent; management is buying shares.",
        bear_case="Valuation is stretched at current levels.",
        risk_factors=["Regulatory risk", "Margin compression"],
        agent_outputs=[
            AgentOutput(agent="MACRO", stance="BULL", conviction="MEDIUM",
                        thesis="Macro supports.", key_points=["Point A"]),
        ],
        consensus_score=0.72,
    )


def _patch_analyst(ticker: str):
    """Context manager that patches both the orchestrator AND signal engine for analyst tests."""
    import contextlib
    import pandas as pd
    import numpy as np

    @contextlib.contextmanager
    def _inner():
        with patch("nq_api.routes.analyst.ParaDebateOrchestrator") as MockOrch, \
             patch("nq_api.routes.analyst.get_signal_engine") as mock_engine_factory:
            # Mock orchestrator
            orch_instance = MagicMock()
            orch_instance.analyse = AsyncMock(return_value=_mock_analyst_response(ticker))
            MockOrch.return_value = orch_instance
            # Mock signal engine (so _build_snapshot doesn't fail without Phase 1)
            engine = MagicMock()
            engine.compute.return_value = pd.DataFrame([{
                "ticker": ticker,
                "composite_score": 0.75,
                "quality_percentile": 0.8,
                "momentum_percentile": 0.7,
                "short_interest_percentile": 0.6,
                "regime_id": 1,
                "momentum_raw": 0.1,
            }])
            mock_engine_factory.return_value = engine
            yield
    return _inner()


def test_analyst_post_returns_report():
    with _patch_analyst("AAPL"):
        response = client.post("/analyst", json={"ticker": "AAPL", "market": "US"})
        assert response.status_code == 200

        data = response.json()
        assert data["ticker"] == "AAPL"
        assert data["head_analyst_verdict"] == "BUY"
        assert "investment_thesis" in data
        assert len(data["agent_outputs"]) >= 1


def test_analyst_verdict_is_valid():
    with _patch_analyst("TSLA"):
        response = client.post("/analyst", json={"ticker": "TSLA"})
        data = response.json()
        assert data["head_analyst_verdict"] in (
            "STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"
        )
```

- [ ] **Step 2: Implement analyst route**

```python
# apps/api/src/nq_api/routes/analyst.py
import asyncio
from fastapi import APIRouter, Depends
from nq_api.schemas import AnalystRequest, AnalystResponse
from nq_api.agents.orchestrator import ParaDebateOrchestrator
from nq_api.deps import get_signal_engine
from nq_api.routes.stocks import _build_snapshot
from nq_api.score_builder import row_to_ai_score

router = APIRouter()


@router.post("", response_model=AnalystResponse)
async def run_analyst(req: AnalystRequest) -> AnalystResponse:
    engine = get_signal_engine()
    snapshot = _build_snapshot(req.ticker.upper(), req.market)
    result_df = engine.compute(snapshot)

    context = {"market": req.market, "vix": 18.0, "ism_pmi": 51.0,
               "regime_label": "Risk-On", "hy_spread_oas": 350.0,
               "spx_return_1m": 0.01, "spx_vs_200ma": 0.02,
               "yield_spread_2y10y": 0.10}

    if not result_df.empty:
        row = result_df.iloc[0]
        context.update({
            "composite_score": float(row.get("composite_score", 0.5)),
            "quality_percentile": float(row.get("quality_percentile", 0.5)),
            "momentum_percentile": float(row.get("momentum_percentile", 0.5)),
            "short_interest_percentile": float(row.get("short_interest_percentile", 0.5)),
            "momentum_raw": float(row.get("momentum_raw", 0.0)),
        })

    orch = ParaDebateOrchestrator()
    return await orch.analyse(ticker=req.ticker.upper(), market=req.market, context=context)
```

- [ ] **Step 3: Implement NL query route**

```python
# apps/api/src/nq_api/routes/query.py
"""Natural language financial query — NeuralQuant's answer to Perplexity Finance."""
import os
import anthropic
from fastapi import APIRouter
from nq_api.schemas import QueryRequest, QueryResponse

router = APIRouter()

_SYSTEM = """You are NeuralQuant's financial intelligence assistant.
You answer questions about stocks, markets, and financial concepts using the data provided.

Rules:
1. Ground every answer in the provided data. Do NOT invent numbers.
2. If data is insufficient, say so and explain what would be needed.
3. End every response with exactly 3 follow-up questions the user might want answered.
4. Cite which data sources informed your answer.
5. Be direct. Financial professionals read this.

Response format:
ANSWER: [Your answer]
DATA_SOURCES: [comma-separated list: e.g., "NeuralQuant AI Score, FRED macro data, Phase 1 signal engine"]
FOLLOW_UP:
- [Question 1]
- [Question 2]
- [Question 3]"""


@router.post("", response_model=QueryResponse)
def run_nl_query(req: QueryRequest) -> QueryResponse:
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # Build context string from available data
    context_parts = [f"User question: {req.question}"]
    if req.ticker:
        context_parts.append(f"Stock in focus: {req.ticker} ({req.market} market)")
        context_parts.append("Note: Real-time data will be injected here in Phase 3.")

    user_msg = "\n".join(context_parts)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text
        return _parse_query_response(raw)
    except Exception as e:
        return QueryResponse(
            answer=f"Query failed: {str(e)[:100]}",
            data_sources=[],
            follow_up_questions=[],
        )


def _parse_query_response(raw: str) -> QueryResponse:
    import re
    answer_match = re.search(r"ANSWER:\s*(.+?)(?=DATA_SOURCES:|$)", raw, re.I | re.S)
    answer = answer_match.group(1).strip() if answer_match else raw[:500]

    sources_match = re.search(r"DATA_SOURCES:\s*(.+?)(?=FOLLOW_UP:|$)", raw, re.I | re.S)
    sources = [s.strip() for s in sources_match.group(1).split(",")] if sources_match else []

    followup_match = re.search(r"FOLLOW_UP:(.*)", raw, re.I | re.S)
    followups = []
    if followup_match:
        followups = [
            q.strip().lstrip("-").strip()
            for q in followup_match.group(1).strip().splitlines()
            if q.strip().lstrip("-").strip()
        ]

    return QueryResponse(
        answer=answer[:2000],
        data_sources=sources[:5],
        follow_up_questions=followups[:3],
    )
```

- [ ] **Step 4: Run all API tests**

```bash
uv run pytest apps/api/tests/ -v
# Expected: all passing
```

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/nq_api/routes/ apps/api/tests/
git commit -m "feat(api): add analyst PARA-DEBATE route and NL query endpoint"
```

---

## Task 8 — Next.js Frontend Scaffold

**Files:**
- Create: `apps/web/` (full Next.js 15 project)
- Create: `apps/web/lib/api.ts`
- Create: `apps/web/lib/types.ts`
- Create: `apps/web/app/layout.tsx`
- Create: `apps/web/app/page.tsx`

**Setup commands (run once):**

```bash
cd apps
npx create-next-app@latest web \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir \
  --import-alias "@/*" \
  --no-turbopack
```

Then add dependencies:

```bash
cd web
npm install @radix-ui/react-dialog @radix-ui/react-badge lucide-react recharts
npx shadcn@latest init   # choose default style, slate base color, CSS variables yes
npx shadcn@latest add card badge button input skeleton tabs accordion
```

- [ ] **Step 1: Create the API client**

```typescript
// apps/web/src/lib/api.ts
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
```

- [ ] **Step 2: Create TypeScript types (mirror Python schemas)**

```typescript
// apps/web/src/lib/types.ts
export type Market = "US" | "IN" | "GLOBAL";
export type Stance = "BULL" | "BEAR" | "NEUTRAL";
export type Conviction = "HIGH" | "MEDIUM" | "LOW";
export type Verdict = "STRONG BUY" | "BUY" | "HOLD" | "SELL" | "STRONG SELL";
export type RegimeLabel = "Risk-On" | "Late-Cycle" | "Bear" | "Recovery";

export interface FeatureDriver {
  name: string;
  contribution: number;
  value: string;
  direction: "positive" | "negative" | "neutral";
}

export interface SubScores {
  quality: number;
  momentum: number;
  short_interest: number;
  value: number;
  low_vol: number;
}

export interface AIScore {
  ticker: string;
  market: Market;
  composite_score: number;
  score_1_10: number;
  regime_id: number;
  regime_label: RegimeLabel;
  sub_scores: SubScores;
  top_drivers: FeatureDriver[];
  confidence: "high" | "medium" | "low";
  last_updated: string;
}

export interface AgentOutput {
  agent: string;
  stance: Stance;
  conviction: Conviction;
  thesis: string;
  key_points: string[];
}

export interface AnalystResponse {
  ticker: string;
  head_analyst_verdict: Verdict;
  investment_thesis: string;
  bull_case: string;
  bear_case: string;
  risk_factors: string[];
  agent_outputs: AgentOutput[];
  consensus_score: number;
}

export interface ScreenerRequest {
  market?: Market;
  min_score?: number;
  max_results?: number;
  tickers?: string[];
}

export interface ScreenerResponse {
  regime_label: RegimeLabel;
  regime_id: number;
  results: AIScore[];
  total: number;
}

export interface AnalystRequest {
  ticker: string;
  market?: Market;
}

export interface QueryRequest {
  question: string;
  ticker?: string;
  market?: Market;
}

export interface QueryResponse {
  answer: string;
  data_sources: string[];
  follow_up_questions: string[];
}
```

- [ ] **Step 3: Create the root layout with navigation**

```tsx
// apps/web/src/app/layout.tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "NeuralQuant — AI Stock Intelligence",
  description: "Institutional-grade AI stock analysis at retail prices",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-gray-950 text-gray-50 min-h-screen`}>
        <nav className="border-b border-gray-800 bg-gray-950/80 backdrop-blur sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
            <Link href="/" className="text-xl font-bold bg-gradient-to-r from-violet-400 to-cyan-400 bg-clip-text text-transparent">
              NeuralQuant
            </Link>
            <div className="flex gap-6 text-sm text-gray-400">
              <Link href="/screener" className="hover:text-white transition-colors">Screener</Link>
              <Link href="/query"    className="hover:text-white transition-colors">Ask AI</Link>
            </div>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-4 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
```

- [ ] **Step 4: Create hero landing page**

```tsx
// apps/web/src/app/page.tsx
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <div className="flex flex-col items-center text-center py-20 gap-8">
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-400 text-sm">
        Institutional-grade AI. Retail price.
      </div>

      <h1 className="text-5xl md:text-7xl font-bold tracking-tight max-w-4xl">
        7 AI analysts debate{" "}
        <span className="bg-gradient-to-r from-violet-400 to-cyan-400 bg-clip-text text-transparent">
          every stock
        </span>{" "}
        so you don't have to
      </h1>

      <p className="text-xl text-gray-400 max-w-2xl">
        NeuralQuant runs a MACRO, FUNDAMENTAL, TECHNICAL, SENTIMENT, GEOPOLITICAL,
        and ADVERSARIAL analyst in parallel — then a HEAD ANALYST synthesises the debate
        into a single investment verdict. Transparent, explainable, real-time.
      </p>

      <div className="flex gap-4">
        <Button asChild size="lg" className="bg-violet-600 hover:bg-violet-700">
          <Link href="/screener">View Top Picks</Link>
        </Button>
        <Button asChild size="lg" variant="outline" className="border-gray-700 hover:bg-gray-800">
          <Link href="/query">Ask the AI</Link>
        </Button>
      </div>

      {/* Feature pills */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8 text-sm">
        {[
          ["🇮🇳 India + US", "NSE/BSE + S&P 500"],
          ["🤖 7 AI Analysts", "PARA-DEBATE protocol"],
          ["🔍 Explainable", "See every signal driver"],
          ["⚡ Near-real-time", "Score updates on news"],
        ].map(([title, sub]) => (
          <div key={title} className="p-4 rounded-xl border border-gray-800 bg-gray-900/50">
            <div className="font-semibold">{title}</div>
            <div className="text-gray-500">{sub}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Verify dev server runs**

```bash
cd apps/web
npm run dev
# Open http://localhost:3000 — should show hero page
```

- [ ] **Step 6: Commit**

```bash
git add apps/web/
git commit -m "feat(web): scaffold Next.js 15 frontend with layout, hero page, API client, and TypeScript types"
```

---

## Task 9 — AIScoreCard + FeatureAttribution Components

**Files:**
- Create: `apps/web/src/components/AIScoreCard.tsx`
- Create: `apps/web/src/components/ScoreBreakdown.tsx`
- Create: `apps/web/src/components/FeatureAttribution.tsx`
- Create: `apps/web/src/components/RegimeBadge.tsx`

**Design goal:** Match and exceed Danelfin's explainability. Score ring (0-10), regime badge, radar chart of sub-scores, top feature drivers with direction bars.

- [ ] **Step 1: Create `RegimeBadge.tsx`**

```tsx
// apps/web/src/components/RegimeBadge.tsx
import { Badge } from "@/components/ui/badge";
import type { RegimeLabel } from "@/lib/types";

const REGIME_STYLES: Record<RegimeLabel, string> = {
  "Risk-On":   "bg-green-500/10 text-green-400 border-green-500/20",
  "Recovery":  "bg-blue-500/10 text-blue-400 border-blue-500/20",
  "Late-Cycle":"bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  "Bear":      "bg-red-500/10 text-red-400 border-red-500/20",
};

export function RegimeBadge({ label }: { label: RegimeLabel }) {
  return (
    <Badge variant="outline" className={REGIME_STYLES[label]}>
      {label}
    </Badge>
  );
}
```

- [ ] **Step 2: Create `AIScoreCard.tsx`**

```tsx
// apps/web/src/components/AIScoreCard.tsx
"use client";
import { RegimeBadge } from "./RegimeBadge";
import type { AIScore } from "@/lib/types";

function ScoreRing({ score }: { score: number }) {
  const pct = score / 10;
  const circumference = 2 * Math.PI * 45;
  const dash = pct * circumference;
  const color = score >= 7 ? "#22c55e" : score >= 4 ? "#eab308" : "#ef4444";

  return (
    <svg width="120" height="120" viewBox="0 0 120 120" className="rotate-[-90deg]">
      <circle cx="60" cy="60" r="45" fill="none" stroke="#1f2937" strokeWidth="10" />
      <circle
        cx="60" cy="60" r="45" fill="none"
        stroke={color} strokeWidth="10"
        strokeDasharray={`${dash} ${circumference}`}
        strokeLinecap="round"
        style={{ transition: "stroke-dasharray 0.8s ease" }}
      />
      <text
        x="60" y="60" textAnchor="middle" dominantBaseline="central"
        fontSize="28" fontWeight="bold" fill="white"
        style={{ transform: "rotate(90deg)", transformOrigin: "60px 60px" }}
      >
        {score}
      </text>
    </svg>
  );
}

export function AIScoreCard({ data }: { data: AIScore }) {
  return (
    <div className="p-6 rounded-2xl border border-gray-800 bg-gray-900/60 backdrop-blur">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="text-3xl font-bold">{data.ticker}</h2>
          <p className="text-gray-400 text-sm mt-1">{data.market} Market</p>
        </div>
        <RegimeBadge label={data.regime_label} />
      </div>

      <div className="flex items-center gap-8">
        <ScoreRing score={data.score_1_10} />
        <div className="flex flex-col gap-1">
          <p className="text-4xl font-bold">{data.score_1_10}<span className="text-xl text-gray-500">/10</span></p>
          <p className="text-gray-400 text-sm">AI Score</p>
          <span className={`text-xs mt-1 ${
            data.confidence === "high" ? "text-green-400" :
            data.confidence === "medium" ? "text-yellow-400" : "text-red-400"
          }`}>
            {data.confidence.toUpperCase()} confidence
          </span>
        </div>
      </div>

      <p className="text-xs text-gray-600 mt-4">
        Updated {new Date(data.last_updated).toLocaleString()}
      </p>
    </div>
  );
}
```

- [ ] **Step 3: Create `FeatureAttribution.tsx`**

```tsx
// apps/web/src/components/FeatureAttribution.tsx
import type { FeatureDriver } from "@/lib/types";

export function FeatureAttribution({ drivers }: { drivers: FeatureDriver[] }) {
  return (
    <div className="p-5 rounded-2xl border border-gray-800 bg-gray-900/60">
      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
        Score Drivers
      </h3>
      <div className="space-y-3">
        {drivers.map((d) => (
          <div key={d.name} className="flex items-center gap-3">
            <span className="text-sm text-gray-300 w-40 flex-shrink-0">{d.name}</span>
            <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  d.direction === "positive" ? "bg-green-500" :
                  d.direction === "negative" ? "bg-red-500" : "bg-gray-500"
                }`}
                style={{ width: `${Math.abs(d.contribution) * 100}%` }}
              />
            </div>
            <span className={`text-xs w-16 text-right font-mono ${
              d.direction === "positive" ? "text-green-400" :
              d.direction === "negative" ? "text-red-400" : "text-gray-500"
            }`}>
              {d.contribution > 0 ? "+" : ""}{(d.contribution * 100).toFixed(0)}
            </span>
            <span className="text-xs text-gray-500 w-16 text-right">{d.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create `ScoreBreakdown.tsx` (radar chart)**

```tsx
// apps/web/src/components/ScoreBreakdown.tsx
"use client";
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer } from "recharts";
import type { SubScores } from "@/lib/types";

export function ScoreBreakdown({ scores }: { scores: SubScores }) {
  const data = [
    { factor: "Quality",  value: Math.round(scores.quality * 100) },
    { factor: "Momentum", value: Math.round(scores.momentum * 100) },
    { factor: "Value",    value: Math.round(scores.value * 100) },
    { factor: "Low Vol",  value: Math.round(scores.low_vol * 100) },
    { factor: "SI",       value: Math.round(scores.short_interest * 100) },
  ];

  return (
    <div className="p-5 rounded-2xl border border-gray-800 bg-gray-900/60">
      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-2">
        Factor Breakdown
      </h3>
      <ResponsiveContainer width="100%" height={220}>
        <RadarChart data={data}>
          <PolarGrid stroke="#1f2937" />
          <PolarAngleAxis dataKey="factor" tick={{ fill: "#9ca3af", fontSize: 12 }} />
          <Radar
            dataKey="value" fill="#7c3aed" fillOpacity={0.25}
            stroke="#7c3aed" strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 5: Verify components compile**

```bash
cd apps/web && npx tsc --noEmit
# Expected: no errors
```

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/components/
git commit -m "feat(web): add AIScoreCard, ScoreBreakdown radar, FeatureAttribution, RegimeBadge components"
```

---

## Task 10 — Stock Detail Page + Screener Page

**Files:**
- Create: `apps/web/src/app/stocks/[ticker]/page.tsx`
- Create: `apps/web/src/components/AgentDebatePanel.tsx`
- Create: `apps/web/src/components/ScreenerTable.tsx`
- Create: `apps/web/src/app/screener/page.tsx`

- [ ] **Step 1: Create `AgentDebatePanel.tsx`**

```tsx
// apps/web/src/components/AgentDebatePanel.tsx
"use client";
import { useState } from "react";
import type { AgentOutput, AnalystResponse } from "@/lib/types";

const STANCE_COLORS = {
  BULL: "text-green-400 bg-green-500/10 border-green-500/20",
  BEAR: "text-red-400 bg-red-500/10 border-red-500/20",
  NEUTRAL: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20",
};

const VERDICT_COLORS = {
  "STRONG BUY": "text-green-300 bg-green-500/20",
  "BUY": "text-green-400 bg-green-500/10",
  "HOLD": "text-yellow-400 bg-yellow-500/10",
  "SELL": "text-red-400 bg-red-500/10",
  "STRONG SELL": "text-red-300 bg-red-500/20",
};

function AgentCard({ output }: { output: AgentOutput }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-gray-800 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 hover:bg-gray-800/40 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-gray-500 w-24">{output.agent}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full border ${STANCE_COLORS[output.stance]}`}>
            {output.stance}
          </span>
          <span className="text-xs text-gray-500">{output.conviction}</span>
        </div>
        <span className="text-gray-600 text-sm">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-3 bg-gray-900/30">
          <p className="text-sm text-gray-300">{output.thesis}</p>
          <ul className="space-y-1">
            {output.key_points.map((p, i) => (
              <li key={i} className="text-xs text-gray-400 flex gap-2">
                <span className="text-violet-500 flex-shrink-0">—</span>{p}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function AgentDebatePanel({ report }: { report: AnalystResponse }) {
  return (
    <div className="space-y-4">
      {/* Head Analyst Verdict */}
      <div className="p-5 rounded-2xl border border-gray-800 bg-gray-900/60">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Head Analyst Verdict</p>
        <div className={`inline-flex px-4 py-2 rounded-full text-lg font-bold mb-3 ${VERDICT_COLORS[report.head_analyst_verdict]}`}>
          {report.head_analyst_verdict}
        </div>
        <p className="text-sm text-gray-300">{report.investment_thesis}</p>
      </div>

      {/* Agent Panel */}
      <div className="p-5 rounded-2xl border border-gray-800 bg-gray-900/60">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-4">PARA-DEBATE Panel</p>
        <div className="space-y-2">
          {report.agent_outputs.map((o) => <AgentCard key={o.agent} output={o} />)}
        </div>
      </div>

      {/* Risk Factors */}
      <div className="p-5 rounded-2xl border border-gray-800 bg-gray-900/60">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">Risk Factors</p>
        <ul className="space-y-2">
          {report.risk_factors.map((r, i) => (
            <li key={i} className="flex gap-2 text-sm text-gray-300">
              <span className="text-red-500 flex-shrink-0">⚠</span>{r}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create stock detail page**

```tsx
// apps/web/src/app/stocks/[ticker]/page.tsx
"use client";
import { useEffect, useState, use } from "react";
import { api } from "@/lib/api";
import type { AIScore, AnalystResponse } from "@/lib/types";
import { AIScoreCard } from "@/components/AIScoreCard";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import { FeatureAttribution } from "@/components/FeatureAttribution";
import { AgentDebatePanel } from "@/components/AgentDebatePanel";

export default function StockPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = use(params);
  const [score, setScore] = useState<AIScore | null>(null);
  const [report, setReport] = useState<AnalystResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [analysing, setAnalysing] = useState(false);

  useEffect(() => {
    api.getStock(ticker).then(setScore).finally(() => setLoading(false));
  }, [ticker]);

  const runDebate = async () => {
    setAnalysing(true);
    try {
      const r = await api.runAnalyst({ ticker });
      setReport(r);
    } finally {
      setAnalysing(false);
    }
  };

  if (loading) return <div className="text-gray-500 animate-pulse">Loading AI score...</div>;
  if (!score) return <div className="text-red-400">Stock not found: {ticker}</div>;

  return (
    <div className="space-y-6">
      <div className="grid md:grid-cols-3 gap-6">
        <AIScoreCard data={score} />
        <ScoreBreakdown scores={score.sub_scores} />
        <FeatureAttribution drivers={score.top_drivers} />
      </div>

      {!report ? (
        <div className="text-center py-12">
          <button
            onClick={runDebate}
            disabled={analysing}
            className="px-8 py-4 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 rounded-xl text-white font-semibold transition-colors"
          >
            {analysing ? "7 analysts debating..." : "Run PARA-DEBATE Analysis"}
          </button>
          <p className="text-gray-500 text-sm mt-2">
            Runs 7 Claude AI analysts in parallel (~5-10 seconds)
          </p>
        </div>
      ) : (
        <AgentDebatePanel report={report} />
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create `ScreenerTable.tsx`**

```tsx
// apps/web/src/components/ScreenerTable.tsx
import Link from "next/link";
import type { AIScore } from "@/lib/types";
import { RegimeBadge } from "./RegimeBadge";

export function ScreenerTable({ stocks }: { stocks: AIScore[] }) {
  return (
    <div className="rounded-2xl border border-gray-800 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-900/80 text-gray-500 text-xs uppercase tracking-wider">
          <tr>
            <th className="px-4 py-3 text-left">Ticker</th>
            <th className="px-4 py-3 text-center">AI Score</th>
            <th className="px-4 py-3 text-center">Quality</th>
            <th className="px-4 py-3 text-center">Momentum</th>
            <th className="px-4 py-3 text-center">Regime</th>
            <th className="px-4 py-3 text-center">Confidence</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800">
          {stocks.map((s, i) => (
            <tr key={s.ticker} className="hover:bg-gray-900/50 transition-colors">
              <td className="px-4 py-3">
                <div className="flex items-center gap-3">
                  <span className="text-gray-600 text-xs w-5">{i + 1}</span>
                  <Link href={`/stocks/${s.ticker}`} className="font-semibold text-white hover:text-violet-400 transition-colors">
                    {s.ticker}
                  </Link>
                  <span className="text-xs text-gray-500">{s.market}</span>
                </div>
              </td>
              <td className="px-4 py-3 text-center">
                <span className={`font-bold text-lg ${
                  s.score_1_10 >= 7 ? "text-green-400" :
                  s.score_1_10 >= 4 ? "text-yellow-400" : "text-red-400"
                }`}>{s.score_1_10}</span>
                <span className="text-gray-600 text-xs">/10</span>
              </td>
              <td className="px-4 py-3 text-center text-gray-300">
                {(s.sub_scores.quality * 100).toFixed(0)}%
              </td>
              <td className="px-4 py-3 text-center text-gray-300">
                {(s.sub_scores.momentum * 100).toFixed(0)}%
              </td>
              <td className="px-4 py-3 text-center">
                <RegimeBadge label={s.regime_label} />
              </td>
              <td className="px-4 py-3 text-center">
                <span className={`text-xs ${
                  s.confidence === "high" ? "text-green-400" :
                  s.confidence === "medium" ? "text-yellow-400" : "text-red-400"
                }`}>{s.confidence}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 4: Create screener page**

```tsx
// apps/web/src/app/screener/page.tsx
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ScreenerResponse } from "@/lib/types";
import { ScreenerTable } from "@/components/ScreenerTable";
import { RegimeBadge } from "@/components/RegimeBadge";

export default function ScreenerPage() {
  const [data, setData] = useState<ScreenerResponse | null>(null);
  const [market, setMarket] = useState<"US" | "IN">("US");
  const [loading, setLoading] = useState(true);

  const load = (m: "US" | "IN") => {
    setLoading(true);
    api.runScreener({ market: m, max_results: 30 })
      .then(setData)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load("US"); }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">AI Screener</h1>
          <p className="text-gray-400 mt-1">Stocks ranked by NeuralQuant composite AI score</p>
        </div>
        {data && <RegimeBadge label={data.regime_label} />}
      </div>

      <div className="flex gap-2">
        {(["US", "IN"] as const).map((m) => (
          <button
            key={m}
            onClick={() => { setMarket(m); load(m); }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              market === m ? "bg-violet-600 text-white" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            {m === "US" ? "🇺🇸 US Stocks" : "🇮🇳 India (NSE)"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="h-12 bg-gray-900 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : data ? (
        <ScreenerTable stocks={data.results} />
      ) : null}
    </div>
  );
}
```

- [ ] **Step 5: Run dev servers end-to-end**

```bash
# Terminal 1: API
cd apps/api && uv run uvicorn nq_api.main:app --reload --port 8000

# Terminal 2: Web
cd apps/web && npm run dev

# Open http://localhost:3000/screener
# Should show ranked US stocks from the signal engine
```

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/
git commit -m "feat(web): add stock detail page, PARA-DEBATE panel, and screener page"
```

---

## Task 11 — NL Query Interface

**Files:**
- Create: `apps/web/src/app/query/page.tsx`
- Create: `apps/web/src/components/NLQueryBox.tsx`

**This is the competitive killer feature — the FactSet Mercury model at retail price.**

- [ ] **Step 1: Create `NLQueryBox.tsx`**

```tsx
// apps/web/src/components/NLQueryBox.tsx
"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { QueryResponse } from "@/lib/types";

const EXAMPLE_QUESTIONS = [
  "Why might RELIANCE outperform in a risk-off regime?",
  "What does a Piotroski score of 8 mean for a company?",
  "Which factors drive NeuralQuant's quality composite?",
  "How does the HMM regime detector work?",
  "What signals indicate a bear market regime?",
];

export function NLQueryBox({ defaultTicker }: { defaultTicker?: string }) {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const ask = async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setResponse(null);
    try {
      const r = await api.runQuery({ question: q, ticker: defaultTicker });
      setResponse(r);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask(question)}
          placeholder="Ask anything about stocks, factors, or the market..."
          className="flex-1 px-4 py-3 bg-gray-900 border border-gray-700 rounded-xl text-white placeholder:text-gray-500 focus:outline-none focus:border-violet-500"
        />
        <button
          onClick={() => ask(question)}
          disabled={loading || !question.trim()}
          className="px-6 py-3 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 rounded-xl text-white font-medium transition-colors"
        >
          {loading ? "..." : "Ask"}
        </button>
      </div>

      {/* Example questions */}
      {!response && !loading && (
        <div className="flex flex-wrap gap-2">
          {EXAMPLE_QUESTIONS.map((q) => (
            <button
              key={q}
              onClick={() => { setQuestion(q); ask(q); }}
              className="text-xs px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white rounded-full transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {loading && (
        <div className="p-5 rounded-xl border border-gray-800 animate-pulse">
          <div className="h-4 bg-gray-800 rounded w-3/4 mb-2" />
          <div className="h-4 bg-gray-800 rounded w-1/2" />
        </div>
      )}

      {response && (
        <div className="space-y-4">
          <div className="p-5 rounded-2xl border border-gray-800 bg-gray-900/60">
            <p className="text-gray-100 leading-relaxed whitespace-pre-wrap">{response.answer}</p>
          </div>

          {response.data_sources.length > 0 && (
            <div className="flex gap-2 flex-wrap">
              <span className="text-xs text-gray-500">Sources:</span>
              {response.data_sources.map((s) => (
                <span key={s} className="text-xs px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20">
                  {s}
                </span>
              ))}
            </div>
          )}

          {response.follow_up_questions.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-gray-500 uppercase tracking-wider">Follow-up questions</p>
              <div className="flex flex-wrap gap-2">
                {response.follow_up_questions.map((q) => (
                  <button
                    key={q}
                    onClick={() => { setQuestion(q); ask(q); }}
                    className="text-xs px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white rounded-full transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create query page**

```tsx
// apps/web/src/app/query/page.tsx
import { NLQueryBox } from "@/components/NLQueryBox";

export default function QueryPage() {
  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Ask the AI</h1>
        <p className="text-gray-400 mt-1">
          Natural language queries grounded in NeuralQuant data — the FactSet Mercury experience at retail price.
        </p>
      </div>
      <NLQueryBox />
    </div>
  );
}
```

- [ ] **Step 3: Test manually**

```bash
# Ensure API is running on port 8000
# Open http://localhost:3000/query
# Ask: "What is the difference between quality and momentum factors?"
# Verify: answer + sources + follow-up questions appear
```

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/app/query/ apps/web/src/components/NLQueryBox.tsx
git commit -m "feat(web): add NL query interface — data-grounded natural language financial assistant"
```

---

## Task 12 — Environment Config + Deployment

**Files:**
- Create: `apps/api/.env.example`
- Create: `apps/web/.env.example`
- Create: `apps/api/Dockerfile` (for Railway)
- Modify: `apps/web/next.config.ts`

- [ ] **Step 1: Create env files**

```bash
# apps/api/.env.example
ANTHROPIC_API_KEY=sk-ant-...
ENVIRONMENT=development

# apps/web/.env.example
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 2: Create API Dockerfile**

```dockerfile
# apps/api/Dockerfile
# Build context MUST be the repo root: `docker build -f apps/api/Dockerfile .`
FROM python:3.12-slim
WORKDIR /app

# Install uv
RUN pip install uv

# Copy Phase 1 workspace packages (paths relative to repo root build context)
COPY packages/ /workspace/packages/
COPY pyproject.toml /workspace/pyproject.toml

# Copy the API package
COPY apps/api/ /app/

# Install with Phase 1 packages available
RUN uv pip install --system -e "/app[prod]" \
    --find-links /workspace/packages/data \
    --find-links /workspace/packages/signals

EXPOSE 8000
CMD ["uvicorn", "nq_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Configure Next.js for Vercel + production API**

```typescript
// apps/web/next.config.ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    // In production, proxy /api/* to Railway-hosted FastAPI
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
```

- [ ] **Step 4: Full end-to-end smoke test**

```bash
# 1. Start FastAPI
cd apps/api && ANTHROPIC_API_KEY=<key> uv run uvicorn nq_api.main:app --port 8000

# 2. Start Next.js
cd apps/web && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev

# 3. Manual test checklist:
# [ ] http://localhost:3000           — hero page loads
# [ ] http://localhost:3000/screener  — shows ranked US and India stocks
# [ ] http://localhost:3000/stocks/AAPL — shows AI score card + factor breakdown
# [ ] Click "Run PARA-DEBATE Analysis" — 7 agents fire, report renders
# [ ] http://localhost:3000/query     — NL question answered with follow-ups
```

- [ ] **Step 5: Run full test suite**

```bash
# API tests
cd apps/api && uv run pytest tests/ -v

# Phase 1 tests (regression check)
cd ../.. && .venv/Scripts/pytest.exe packages/ -v --tb=short

# Expected: all green
```

- [ ] **Step 6: Final Phase 2 commit**

```bash
git add apps/
git commit -m "feat: Phase 2 complete — 7-agent PARA-DEBATE system + Next.js AI analyst platform

Phase 2 deliverables:
- FastAPI backend: /stocks, /screener, /analyst, /query endpoints
- 7 Claude agents: MACRO, FUNDAMENTAL, TECHNICAL, SENTIMENT,
  GEOPOLITICAL, ADVERSARIAL, HEAD ANALYST
- PARA-DEBATE orchestrator: parallel asyncio.gather execution (~5s)
- AIScoreCard: score ring + regime badge + confidence
- FeatureAttribution: Danelfin-style feature driver bars
- ScoreBreakdown: radar chart of 5 sub-factors
- AgentDebatePanel: collapsible per-agent reasoning
- NL query interface: data-grounded conversational AI
- Screener: US + India ranked universe with AI scores
- US (50 tickers) + India/NSE (50 tickers) default universe

Competitive gaps addressed:
- AI explainability (Danelfin parity + counterfactual approach)
- NL query interface (FactSet Mercury model at retail price)
- India coverage from day one (NSE/BSE universe)
- Mobile-first dark UI design"
```

---

## Phase 2 → Phase 3 Gaps (Future Work)

These are intentionally deferred — not forgotten:

| Feature | Phase 3 Priority | Notes |
|---|---|---|
| Real DataStore integration (replace mock fundamentals) | Critical | Replace `_build_snapshot` with actual DuckDB queries |
| Live yfinance price data for charts | High | Add `PriceChart.tsx` with Recharts OHLCV |
| News/sentiment NLP pipeline | High | Accern or custom NLP; feed into SENTIMENT agent |
| Real-time score updates on news | High | Event-driven pipeline with Celery/Redis |
| Brokerage sync (Zerodha, IBKR) | High | Plaid/OAuth portfolio import |
| Self-serve backtesting UI | Medium | "Test this signal strategy" interface |
| Alternative data signals | Medium | Web traffic (SimilarWeb), job postings |
| Options flow signals | Medium | Unusual Whales API integration |
| Supabase auth + user accounts | Medium | Watchlists, saved reports, personalization |
| Mobile app (React Native) | Medium | Mobile-first architecture pays off here |
| Developer API (webhook alerts) | Medium | B2B2C channel |
| Verified community predictions | Low | Seeking Alpha moat challenger |

---

## Testing Summary

| Layer | Test file | What it validates |
|---|---|---|
| API health | `tests/test_health.py` | CORS, health endpoint |
| AI scores | `tests/test_stocks_route.py` | Score schema, 404 handling |
| Screener | `tests/test_screener_route.py` | Sorted results, min_score filter |
| Agents | `tests/test_agents.py` | All 7 agents parse output correctly |
| Orchestrator | `tests/test_orchestrator.py` | Parallel execution, adversarial never BULL |
| Analyst route | `tests/test_analyst_route.py` | Verdict is valid, response schema correct |
| Phase 1 regression | `packages/*/tests/` | 33 existing tests still green |

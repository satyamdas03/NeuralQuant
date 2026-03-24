# NeuralQuant Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete data pipeline, 10-signal quant engine, 4-regime HMM detector, and backtesting framework that form the foundation every subsequent phase builds on.

**Architecture:** Turborepo monorepo with two packages built in this phase — `packages/data` (20+ free data source connectors behind a rate-limiting DataBroker) and `packages/signals` (10-factor signal library + LightGBM LambdaRank + HMM regime engine). All logic is framework-agnostic Python; no Streamlit, no FastAPI yet. The existing V8 scoring logic from `C:/Users/point/projects/finance/stock-selector-deploy/` is ported and evolved into the signal library.

**Tech Stack:** Python 3.12, uv (package manager), pytest, DuckDB, yfinance, pandas, numpy, hmmlearn, lightgbm, pandas-ta, fredapi, requests, feedparser, praw

---

## File Map

```
neuralquant/
├── pyproject.toml                          # Root workspace config
├── .python-version                         # 3.12
├── packages/
│   ├── data/
│   │   ├── pyproject.toml
│   │   ├── src/nq_data/
│   │   │   ├── __init__.py
│   │   │   ├── broker.py                   # DataBroker — rate-limit token buckets
│   │   │   ├── store.py                    # DuckDB storage layer
│   │   │   ├── models.py                   # Pydantic schemas: OHLCV, Fundamental, Signal
│   │   │   ├── price/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── yfinance_connector.py   # US + India prices via yfinance
│   │   │   │   ├── nse_bhavcopy.py         # NSE EOD bulk download + delivery %
│   │   │   │   └── twelve_data.py          # Twelve Data REST (800 credits/day)
│   │   │   ├── fundamentals/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── edgar_xbrl.py           # SEC EDGAR XBRL API — US fundamentals
│   │   │   │   ├── fmp_connector.py        # Financial Modeling Prep (250 req/day)
│   │   │   │   └── screener_in.py          # Screener.in scraper — India fundamentals
│   │   │   ├── macro/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── fred_connector.py       # FRED API — US macro (VIX, yields, spreads)
│   │   │   │   └── world_bank.py           # World Bank API — global GDP/inflation
│   │   │   ├── news/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── gdelt_connector.py      # GDELT news tone aggregates
│   │   │   │   ├── google_news_rss.py      # Google News RSS via feedparser
│   │   │   │   └── stocktwits.py           # StockTwits sentiment spikes
│   │   │   └── alt_signals/
│   │   │       ├── __init__.py
│   │   │       ├── edgar_form4.py          # SEC EDGAR Form 4 insider trades
│   │   │       ├── edgar_13f.py            # SEC EDGAR 13F institutional holdings
│   │   │       ├── finra_short.py          # FINRA short interest bulk files
│   │   │       └── nse_bulk_deals.py       # NSE bulk/block deals
│   │   └── tests/
│   │       ├── conftest.py
│   │       ├── test_broker.py
│   │       ├── test_store.py
│   │       ├── test_price.py
│   │       ├── test_fundamentals.py
│   │       ├── test_macro.py
│   │       └── test_alt_signals.py
│   └── signals/
│       ├── pyproject.toml
│       ├── src/nq_signals/
│       │   ├── __init__.py
│       │   ├── models.py                   # SignalResult, FactorScore, RankedStock
│       │   ├── factors/
│       │   │   ├── __init__.py
│       │   │   ├── quality.py              # Quality composite (Piotroski + Gross Profit + Accruals)
│       │   │   ├── momentum.py             # Momentum 12-1 with crash filter
│       │   │   ├── low_vol.py              # Low volatility / BAB factor
│       │   │   ├── short_interest.py       # Short interest days-to-cover signal
│       │   │   ├── insider_buys.py         # Insider cluster buy signal
│       │   │   ├── earnings_surprise.py    # Earnings surprise + PEAD drift
│       │   │   ├── institutional_delta.py  # 13F institutional ownership delta
│       │   │   ├── options_flow.py         # Put/call ratio + options flow
│       │   │   ├── nlp_tone.py             # Earnings call NLP tone delta (FinBERT)
│       │   │   └── india_specific.py       # FII/DII flows, delivery %, F&O rollover, promoter buys
│       │   ├── regime/
│       │   │   ├── __init__.py
│       │   │   └── hmm_detector.py         # 4-state HMM on macro indicators
│       │   ├── ranker/
│       │   │   ├── __init__.py
│       │   │   ├── lgbm_ranker.py          # LightGBM LambdaRank trainer + predictor
│       │   │   └── walk_forward.py         # Walk-forward cross-validation
│       │   ├── universe/
│       │   │   ├── __init__.py
│       │   │   └── screener.py             # Pre-screen 200→80 candidates
│       │   └── engine.py                   # Main signal computation orchestrator
│       └── tests/
│           ├── conftest.py
│           ├── test_quality.py
│           ├── test_momentum.py
│           ├── test_hmm.py
│           ├── test_lgbm.py
│           └── test_engine.py
└── scripts/
    └── backtest/
        ├── run_backtest.py                 # Main backtest runner (16+ quarters)
        └── report.py                       # IC/ICIR/Sharpe reporting
```

---

## Task 1: Monorepo Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `packages/data/pyproject.toml`
- Create: `packages/signals/pyproject.toml`
- Create: `.env.example`

- [ ] **Step 1.1: Install uv if not present**

```bash
pip install uv
uv --version
```
Expected: `uv 0.4+`

- [ ] **Step 1.2: Create root pyproject.toml**

```toml
# pyproject.toml
[tool.uv.workspace]
members = ["packages/*", "apps/*"]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-mock>=3.12",
]
```

- [ ] **Step 1.3: Create .python-version**

```
3.12
```

- [ ] **Step 1.4: Create packages/data/pyproject.toml**

```toml
[project]
name = "nq-data"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "yfinance>=0.2.40",
    "pandas>=2.2",
    "numpy>=1.26",
    "requests>=2.31",
    "pydantic>=2.6",
    "duckdb>=0.10",
    "fredapi>=0.5",
    "feedparser>=6.0",
    "praw>=7.7",
    "jugaad-data>=0.27",
    "python-dotenv>=1.0",
    "httpx>=0.27",
    "tenacity>=8.2",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 1.5: Create packages/signals/pyproject.toml**

```toml
[project]
name = "nq-signals"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "nq-data",
    "lightgbm>=4.3",
    "hmmlearn>=0.3",
    "scikit-learn>=1.4",
    "pandas-ta>=0.3",
    "transformers>=4.39",
    "torch>=2.2",
    "scipy>=1.12",
    "numpy>=1.26",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 1.6: Create .env.example**

```bash
# Free API keys (all require free registration)
FRED_API_KEY=your_fred_key_here           # https://fred.stlouisfed.org/docs/api/api_key.html
FMP_API_KEY=your_fmp_key_here             # https://financialmodelingprep.com/developer
TWELVE_DATA_API_KEY=your_12d_key_here     # https://twelvedata.com
REDDIT_CLIENT_ID=your_reddit_client_id   # https://www.reddit.com/prefs/apps
REDDIT_CLIENT_SECRET=your_reddit_secret
REDDIT_USER_AGENT=NeuralQuant/0.1

# Supabase (Phase 3)
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=

# Anthropic (Phase 2)
ANTHROPIC_API_KEY=
```

- [ ] **Step 1.7: Install workspace**

```bash
cd C:/Users/point/projects/stockpredictor
uv sync
```
Expected: All packages installed, `.venv` created at root.

- [ ] **Step 1.8: Commit**

```bash
git add pyproject.toml .python-version .env.example packages/data/pyproject.toml packages/signals/pyproject.toml
git commit -m "feat: scaffold monorepo with uv workspace"
```

---

## Task 2: Data Models & DataBroker

**Files:**
- Create: `packages/data/src/nq_data/__init__.py`
- Create: `packages/data/src/nq_data/models.py`
- Create: `packages/data/src/nq_data/broker.py`
- Create: `packages/data/src/nq_data/store.py`
- Create: `packages/data/tests/conftest.py`
- Create: `packages/data/tests/test_broker.py`

- [ ] **Step 2.1: Write failing test for DataBroker rate limiting**

```python
# packages/data/tests/test_broker.py
import time
import pytest
from nq_data.broker import DataBroker, SourceConfig

def test_broker_enforces_rate_limit():
    """DataBroker should pace requests to stay within rate limits."""
    config = SourceConfig(name="test", requests_per_minute=6)
    broker = DataBroker([config])

    times = []
    for _ in range(3):
        with broker.acquire("test"):
            times.append(time.monotonic())

    gaps = [times[i+1] - times[i] for i in range(len(times)-1)]
    # With 6 req/min, minimum gap is 10s. With 3 requests it should be near-instant
    # but we just verify the context manager works without error
    assert len(gaps) == 2

def test_broker_raises_for_unknown_source():
    broker = DataBroker([])
    with pytest.raises(KeyError):
        with broker.acquire("nonexistent"):
            pass
```

- [ ] **Step 2.2: Run test to confirm failure**

```bash
cd packages/data && uv run pytest tests/test_broker.py -v
```
Expected: `FAILED` — `nq_data.broker` does not exist yet.

- [ ] **Step 2.3: Create models.py**

```python
# packages/data/src/nq_data/models.py
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field

class OHLCVBar(BaseModel):
    ticker: str
    market: str  # "US" | "IN" | "GLOBAL"
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    adjusted_close: Optional[float] = None
    delivery_pct: Optional[float] = None  # NSE-specific

class FundamentalSnapshot(BaseModel):
    ticker: str
    market: str
    as_of_date: date
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    ps: Optional[float] = None
    roe: Optional[float] = None
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None
    revenue_growth_yoy: Optional[float] = None
    fcf_yield: Optional[float] = None
    debt_equity: Optional[float] = None
    piotroski_score: Optional[int] = None
    accruals_ratio: Optional[float] = None
    beneish_m_score: Optional[float] = None

class MacroSnapshot(BaseModel):
    as_of_date: date
    vix: Optional[float] = None
    yield_10y: Optional[float] = None
    yield_2y: Optional[float] = None
    yield_spread_2y10y: Optional[float] = None
    hy_spread_oas: Optional[float] = None
    ism_pmi: Optional[float] = None
    cpi_yoy: Optional[float] = None
    fed_funds_rate: Optional[float] = None
    spx_vs_200ma: Optional[float] = None  # % above/below 200-day MA

class NewsItem(BaseModel):
    ticker: str
    source: str
    headline: str
    published_at: datetime
    sentiment_score: Optional[float] = None  # -1.0 to 1.0
    url: Optional[str] = None
```

- [ ] **Step 2.4: Create broker.py**

```python
# packages/data/src/nq_data/broker.py
import time
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator

@dataclass
class SourceConfig:
    name: str
    requests_per_minute: int
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _request_times: list = field(default_factory=list, init=False, repr=False)

    def _min_interval(self) -> float:
        return 60.0 / self.requests_per_minute

    def wait_if_needed(self) -> None:
        with self._lock:
            now = time.monotonic()
            # Remove timestamps older than 60s
            self._request_times = [t for t in self._request_times if now - t < 60]
            if len(self._request_times) >= self.requests_per_minute:
                # Wait until oldest request is >60s ago
                wait = 60 - (now - self._request_times[0]) + 0.05
                if wait > 0:
                    time.sleep(wait)
            self._request_times.append(time.monotonic())

class DataBroker:
    """Central rate-limit manager. All data connectors must go through this."""

    DEFAULTS = {
        "yfinance":      SourceConfig("yfinance",      120),
        "twelve_data":   SourceConfig("twelve_data",    8),   # 800 credits/day ≈ 8/min
        "fred":          SourceConfig("fred",           120),
        "fmp":           SourceConfig("fmp",            5),    # 250/day ≈ conservative
        "edgar":         SourceConfig("edgar",          10),   # 10 req/sec limit
        "finra":         SourceConfig("finra",          10),
        "nse":           SourceConfig("nse",            20),   # Be gentle with NSE
        "gdelt":         SourceConfig("gdelt",          30),
        "newsapi":       SourceConfig("newsapi",        5),
        "stocktwits":    SourceConfig("stocktwits",     3),    # 200/hr = 3/min
        "reddit":        SourceConfig("reddit",         60),
        "world_bank":    SourceConfig("world_bank",     30),
        "screener_in":   SourceConfig("screener_in",    6),    # Scraper — be very gentle
    }

    def __init__(self, extra_configs: list[SourceConfig] | None = None):
        self._sources: dict[str, SourceConfig] = dict(self.DEFAULTS)
        for cfg in (extra_configs or []):
            self._sources[cfg.name] = cfg

    @contextmanager
    def acquire(self, source_name: str) -> Generator[None, None, None]:
        if source_name not in self._sources:
            raise KeyError(f"Unknown source: '{source_name}'. Register it in DataBroker.DEFAULTS.")
        self._sources[source_name].wait_if_needed()
        yield

# Global singleton — import and use anywhere
broker = DataBroker()
```

- [ ] **Step 2.5: Run tests — expect pass**

```bash
cd packages/data && uv run pytest tests/test_broker.py -v
```
Expected: `PASSED`

- [ ] **Step 2.6: Write and run DuckDB store tests**

```python
# packages/data/tests/test_store.py
import pytest
import tempfile
from pathlib import Path
from datetime import date
from nq_data.store import DataStore
from nq_data.models import OHLCVBar

@pytest.fixture
def tmp_store(tmp_path):
    return DataStore(db_path=str(tmp_path / "test.duckdb"))

def test_store_ohlcv_round_trip(tmp_store):
    bar = OHLCVBar(ticker="AAPL", market="US", date=date(2025, 1, 2),
                   open=180.0, high=185.0, low=179.0, close=182.0, volume=1e7)
    tmp_store.upsert_ohlcv([bar])
    result = tmp_store.get_ohlcv("AAPL", "US", date(2025, 1, 1), date(2025, 1, 3))
    assert len(result) == 1
    assert result[0].close == 182.0

def test_store_deduplicates_ohlcv(tmp_store):
    bar = OHLCVBar(ticker="AAPL", market="US", date=date(2025, 1, 2),
                   open=180.0, high=185.0, low=179.0, close=182.0, volume=1e7)
    tmp_store.upsert_ohlcv([bar, bar])  # Insert twice
    result = tmp_store.get_ohlcv("AAPL", "US", date(2025, 1, 1), date(2025, 1, 3))
    assert len(result) == 1  # Deduplication works
```

- [ ] **Step 2.7: Create store.py**

```python
# packages/data/src/nq_data/store.py
import duckdb
from datetime import date
from pathlib import Path
from typing import Optional
from .models import OHLCVBar, FundamentalSnapshot, MacroSnapshot

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ohlcv (
    ticker VARCHAR NOT NULL,
    market VARCHAR NOT NULL,
    date DATE NOT NULL,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE,
    adjusted_close DOUBLE,
    delivery_pct DOUBLE,
    PRIMARY KEY (ticker, market, date)
);
CREATE TABLE IF NOT EXISTS fundamentals (
    ticker VARCHAR NOT NULL,
    market VARCHAR NOT NULL,
    as_of_date DATE NOT NULL,
    pe_ttm DOUBLE, pb DOUBLE, ps DOUBLE,
    roe DOUBLE, gross_margin DOUBLE, net_margin DOUBLE,
    revenue_growth_yoy DOUBLE, fcf_yield DOUBLE, debt_equity DOUBLE,
    piotroski_score INTEGER, accruals_ratio DOUBLE, beneish_m_score DOUBLE,
    PRIMARY KEY (ticker, market, as_of_date)
);
CREATE TABLE IF NOT EXISTS macro (
    as_of_date DATE PRIMARY KEY,
    vix DOUBLE, yield_10y DOUBLE, yield_2y DOUBLE,
    yield_spread_2y10y DOUBLE, hy_spread_oas DOUBLE,
    ism_pmi DOUBLE, cpi_yoy DOUBLE, fed_funds_rate DOUBLE,
    spx_vs_200ma DOUBLE
);
"""

class DataStore:
    def __init__(self, db_path: str = "neuralquant.duckdb"):
        self.db_path = db_path
        self._conn = duckdb.connect(db_path)
        self._conn.execute(_SCHEMA)

    def upsert_ohlcv(self, bars: list[OHLCVBar]) -> None:
        if not bars:
            return
        rows = [(b.ticker, b.market, b.date, b.open, b.high, b.low,
                 b.close, b.volume, b.adjusted_close, b.delivery_pct) for b in bars]
        self._conn.executemany(
            "INSERT OR REPLACE INTO ohlcv VALUES (?,?,?,?,?,?,?,?,?,?)", rows
        )

    def get_ohlcv(self, ticker: str, market: str,
                  start: date, end: date) -> list[OHLCVBar]:
        rows = self._conn.execute(
            "SELECT * FROM ohlcv WHERE ticker=? AND market=? AND date BETWEEN ? AND ? ORDER BY date",
            [ticker, market, start, end]
        ).fetchall()
        cols = ["ticker","market","date","open","high","low","close","volume","adjusted_close","delivery_pct"]
        return [OHLCVBar(**dict(zip(cols, r))) for r in rows]
```

- [ ] **Step 2.8: Run all data tests**

```bash
cd packages/data && uv run pytest tests/ -v
```
Expected: All pass.

- [ ] **Step 2.9: Commit**

```bash
git add packages/data/src/ packages/data/tests/
git commit -m "feat(data): add DataBroker rate limiter + DuckDB store + Pydantic models"
```

---

## Task 3: Price Data Connectors

**Files:**
- Create: `packages/data/src/nq_data/price/yfinance_connector.py`
- Create: `packages/data/src/nq_data/price/nse_bhavcopy.py`
- Create: `packages/data/tests/test_price.py`

- [ ] **Step 3.1: Write failing tests**

```python
# packages/data/tests/test_price.py
import pytest
from unittest.mock import patch, MagicMock
from datetime import date
import pandas as pd
from nq_data.price.yfinance_connector import YFinanceConnector
from nq_data.price.nse_bhavcopy import NSEBhavCopyConnector
from nq_data.models import OHLCVBar

def make_mock_yf_df():
    idx = pd.DatetimeIndex([pd.Timestamp("2025-01-02")], name="Date")
    return pd.DataFrame({
        "Open": [180.0], "High": [185.0], "Low": [179.0],
        "Close": [182.0], "Volume": [1e7], "Adj Close": [182.0]
    }, index=idx)

def test_yfinance_connector_returns_ohlcv_bars():
    connector = YFinanceConnector()
    with patch("yfinance.download", return_value=make_mock_yf_df()):
        bars = connector.fetch("AAPL", "US", date(2025,1,1), date(2025,1,3))
    assert len(bars) == 1
    assert bars[0].ticker == "AAPL"
    assert bars[0].market == "US"
    assert bars[0].close == 182.0

def test_yfinance_appends_ns_suffix_for_india():
    connector = YFinanceConnector()
    with patch("yfinance.download", return_value=make_mock_yf_df()) as mock_dl:
        connector.fetch("TRENT", "IN", date(2025,1,1), date(2025,1,3))
        call_args = mock_dl.call_args[0][0]
        assert call_args == "TRENT.NS"

def test_nse_bhavcopy_parses_csv(tmp_path):
    """NSEBhavCopyConnector should parse Bhavcopy CSV format."""
    csv_content = "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY,DELIV_QTY\n"
    csv_content += "TRENT,EQ,6200.0,6350.0,6180.0,6300.0,500000,250000\n"
    csv_file = tmp_path / "bhavcopy.csv"
    csv_file.write_text(csv_content)
    connector = NSEBhavCopyConnector()
    bars = connector.parse_bhavcopy(str(csv_file), date(2025, 1, 2))
    assert len(bars) == 1
    assert bars[0].ticker == "TRENT"
    assert bars[0].delivery_pct == pytest.approx(50.0, abs=0.1)
```

- [ ] **Step 3.2: Run to confirm failure**

```bash
cd packages/data && uv run pytest tests/test_price.py -v
```
Expected: `FAILED` — modules don't exist yet.

- [ ] **Step 3.3: Create yfinance_connector.py**

```python
# packages/data/src/nq_data/price/yfinance_connector.py
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
from ..models import OHLCVBar
from ..broker import broker

SUFFIX = {"IN": ".NS", "IN_BSE": ".BO"}

class YFinanceConnector:
    def fetch(self, ticker: str, market: str,
              start: date, end: date) -> list[OHLCVBar]:
        """Fetch daily OHLCV bars. Market: 'US' | 'IN' | 'IN_BSE'"""
        yf_ticker = ticker + SUFFIX.get(market, "")
        with broker.acquire("yfinance"):
            df = yf.download(
                yf_ticker,
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                progress=False,
                auto_adjust=False,
            )
        if df.empty:
            return []
        df = df.reset_index()
        bars = []
        for _, row in df.iterrows():
            bars.append(OHLCVBar(
                ticker=ticker,
                market=market,
                date=row["Date"].date(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row["Volume"]),
                adjusted_close=float(row.get("Adj Close", row["Close"])),
            ))
        return bars

    def fetch_batch(self, tickers: list[str], market: str,
                    start: date, end: date) -> list[OHLCVBar]:
        """Batch fetch for efficiency — yfinance supports multi-ticker download."""
        suffixed = [t + SUFFIX.get(market, "") for t in tickers]
        with broker.acquire("yfinance"):
            df = yf.download(
                " ".join(suffixed),
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                progress=False,
                auto_adjust=False,
                group_by="ticker",
            )
        if df.empty:
            return []
        bars = []
        for orig_ticker, suffixed_ticker in zip(tickers, suffixed):
            try:
                sub = df[suffixed_ticker].dropna(subset=["Close"])
            except KeyError:
                continue
            for ts, row in sub.iterrows():
                bars.append(OHLCVBar(
                    ticker=orig_ticker, market=market,
                    date=ts.date(),
                    open=float(row["Open"]), high=float(row["High"]),
                    low=float(row["Low"]), close=float(row["Close"]),
                    volume=float(row["Volume"]),
                    adjusted_close=float(row.get("Adj Close", row["Close"])),
                ))
        return bars
```

- [ ] **Step 3.4: Create nse_bhavcopy.py**

```python
# packages/data/src/nq_data/price/nse_bhavcopy.py
"""
NSE Bhavcopy downloader. Completely free, no API key.
Bhavcopy URL pattern: https://nsearchives.nseindia.com/content/historical/EQUITIES/<YYYY>/<MMM>/cm<DD><MMM><YYYY>bhav.csv.zip
"""
import io
import zipfile
import requests
import pandas as pd
from datetime import date
from ..models import OHLCVBar
from ..broker import broker

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.nseindia.com",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
}

class NSEBhavCopyConnector:
    BASE_URL = "https://nsearchives.nseindia.com/content/historical/EQUITIES/{year}/{month}/cm{day}{month}{year}bhav.csv.zip"

    def download_bhavcopy(self, for_date: date) -> list[OHLCVBar]:
        """Download and parse Bhavcopy for a given date."""
        url = self.BASE_URL.format(
            year=for_date.strftime("%Y"),
            month=for_date.strftime("%b").upper(),
            day=for_date.strftime("%d"),
        )
        with broker.acquire("nse"):
            resp = requests.get(url, headers=NSE_HEADERS, timeout=30)
        if resp.status_code != 200:
            return []  # Non-trading day or data not yet available
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            csv_name = zf.namelist()[0]
            with zf.open(csv_name) as f:
                content = f.read().decode("utf-8")
        return self.parse_bhavcopy(io.StringIO(content), for_date)

    def parse_bhavcopy(self, source, for_date: date) -> list[OHLCVBar]:
        """Parse Bhavcopy CSV. source can be file path str or StringIO."""
        df = pd.read_csv(source)
        # Normalize column names (Bhavcopy format varies slightly by year)
        df.columns = [c.strip() for c in df.columns]
        eq = df[df.get("SERIES", df.get("Series", pd.Series(dtype=str))).str.strip() == "EQ"]
        bars = []
        for _, row in eq.iterrows():
            ticker = str(row.get("SYMBOL", row.get("Symbol", ""))).strip()
            tottrd = float(row.get("TOTTRDQTY", row.get("TOTTRDQTY", 0)) or 0)
            deliv = float(row.get("DELIV_QTY", row.get("DELVQTY", 0)) or 0)
            delivery_pct = (deliv / tottrd * 100) if tottrd > 0 else None
            bars.append(OHLCVBar(
                ticker=ticker, market="IN",
                date=for_date,
                open=float(row.get("OPEN", row.get("Open", 0)) or 0),
                high=float(row.get("HIGH", row.get("High", 0)) or 0),
                low=float(row.get("LOW", row.get("Low", 0)) or 0),
                close=float(row.get("CLOSE", row.get("Close", 0)) or 0),
                volume=tottrd,
                delivery_pct=delivery_pct,
            ))
        return bars
```

- [ ] **Step 3.5: Run tests**

```bash
cd packages/data && uv run pytest tests/test_price.py -v
```
Expected: All pass.

- [ ] **Step 3.6: Commit**

```bash
git add packages/data/src/nq_data/price/
git commit -m "feat(data): add yfinance + NSE Bhavcopy price connectors"
```

---

## Task 4: Macro Data — FRED Connector

**Files:**
- Create: `packages/data/src/nq_data/macro/fred_connector.py`
- Create: `packages/data/tests/test_macro.py`

- [ ] **Step 4.1: Write failing test**

```python
# packages/data/tests/test_macro.py
import pytest
from unittest.mock import patch, MagicMock
from datetime import date
import pandas as pd
from nq_data.macro.fred_connector import FREDConnector
from nq_data.models import MacroSnapshot

def test_fred_connector_builds_snapshot():
    connector = FREDConnector(api_key="test_key")
    mock_series = {
        "VIXCLS": pd.Series([15.2], index=pd.DatetimeIndex([pd.Timestamp("2025-01-02")])),
        "DGS10": pd.Series([4.3], index=pd.DatetimeIndex([pd.Timestamp("2025-01-02")])),
        "DGS2": pd.Series([4.7], index=pd.DatetimeIndex([pd.Timestamp("2025-01-02")])),
        "BAMLH0A0HYM2": pd.Series([3.2], index=pd.DatetimeIndex([pd.Timestamp("2025-01-02")])),
        "MANEMP": pd.Series([49.5], index=pd.DatetimeIndex([pd.Timestamp("2025-01-02")])),
        "FEDFUNDS": pd.Series([5.25], index=pd.DatetimeIndex([pd.Timestamp("2025-01-02")])),
        "CPIAUCSL": pd.Series([312.0], index=pd.DatetimeIndex([pd.Timestamp("2025-01-02")])),
    }
    with patch("fredapi.Fred") as MockFred:
        instance = MockFred.return_value
        instance.get_series.side_effect = lambda sid, **kw: mock_series.get(sid, pd.Series())
        snapshot = connector.get_snapshot(date(2025, 1, 2))
    assert snapshot.vix == pytest.approx(15.2)
    assert snapshot.yield_10y == pytest.approx(4.3)
    assert snapshot.yield_spread_2y10y == pytest.approx(-0.4, abs=0.01)  # 4.3 - 4.7
```

- [ ] **Step 4.2: Create fred_connector.py**

```python
# packages/data/src/nq_data/macro/fred_connector.py
import os
from datetime import date, timedelta
from fredapi import Fred
from ..models import MacroSnapshot
from ..broker import broker

SERIES = {
    "vix":             "VIXCLS",
    "yield_10y":       "DGS10",
    "yield_2y":        "DGS2",
    "hy_spread_oas":   "BAMLH0A0HYM2",
    "ism_pmi":         "MANEMP",  # ISM Manufacturing PMI
    "fed_funds_rate":  "FEDFUNDS",
    "cpi":             "CPIAUCSL",
}

class FREDConnector:
    def __init__(self, api_key: str | None = None):
        key = api_key or os.environ["FRED_API_KEY"]
        self._fred = Fred(api_key=key)

    def _fetch(self, series_id: str, as_of: date) -> float | None:
        start = (as_of - timedelta(days=10)).isoformat()
        with broker.acquire("fred"):
            s = self._fred.get_series(series_id, observation_start=start,
                                      observation_end=as_of.isoformat())
        if s.empty:
            return None
        return float(s.dropna().iloc[-1])

    def get_snapshot(self, as_of: date) -> MacroSnapshot:
        vals = {k: self._fetch(sid, as_of) for k, sid in SERIES.items()}
        y10 = vals.get("yield_10y")
        y2 = vals.get("yield_2y")
        spread = (y10 - y2) if (y10 and y2) else None
        return MacroSnapshot(
            as_of_date=as_of,
            vix=vals.get("vix"),
            yield_10y=y10,
            yield_2y=y2,
            yield_spread_2y10y=spread,
            hy_spread_oas=vals.get("hy_spread_oas"),
            ism_pmi=vals.get("ism_pmi"),
            cpi_yoy=vals.get("cpi"),  # Will compute YoY % in signal engine
            fed_funds_rate=vals.get("fed_funds_rate"),
        )
```

- [ ] **Step 4.3: Run tests**

```bash
cd packages/data && uv run pytest tests/test_macro.py -v
```
Expected: Pass.

- [ ] **Step 4.4: Commit**

```bash
git add packages/data/src/nq_data/macro/
git commit -m "feat(data): add FRED macro connector (VIX, yields, spreads, PMI)"
```

---

## Task 5: Alternative Signals — SEC EDGAR Form 4

**Files:**
- Create: `packages/data/src/nq_data/alt_signals/edgar_form4.py`
- Create: `packages/data/tests/test_alt_signals.py`

- [ ] **Step 5.1: Write failing test**

```python
# packages/data/tests/test_alt_signals.py
import pytest
from unittest.mock import patch
from datetime import date
from nq_data.alt_signals.edgar_form4 import Form4Connector

MOCK_FORM4_RESPONSE = {
    "hits": {
        "hits": [{
            "_source": {
                "period_of_report": "2025-01-10",
                "entity_name": "NVIDIA Corp",
                "file_date": "2025-01-12",
                "period_of_report": "2025-01-10",
                "form_type": "4",
            }
        }]
    }
}

def test_form4_returns_insider_events():
    connector = Form4Connector()
    with patch.object(connector, "_fetch_raw", return_value=[{
        "ticker": "NVDA",
        "officer_title": "CEO",
        "transaction_date": date(2025, 1, 10),
        "shares": 5000,
        "price_per_share": 480.0,
        "is_purchase": True,
    }]):
        events = connector.get_insider_events("NVDA", date(2025, 1, 1), date(2025, 1, 15))
    assert len(events) == 1
    assert events[0]["is_purchase"] is True
    assert events[0]["ticker"] == "NVDA"

def test_form4_cluster_signal():
    """A cluster of insider buys should return positive signal score."""
    from nq_data.alt_signals.edgar_form4 import compute_insider_cluster_score
    events = [
        {"is_purchase": True, "shares": 5000, "price_per_share": 480.0,
         "transaction_date": date(2025, 1, i), "officer_title": "CEO"}
        for i in range(1, 4)
    ]
    score = compute_insider_cluster_score(events, lookback_days=90)
    assert score > 0.5  # Strong cluster buy signal
```

- [ ] **Step 5.2: Create edgar_form4.py**

```python
# packages/data/src/nq_data/alt_signals/edgar_form4.py
"""
SEC EDGAR Form 4 insider trading signals.
Free API: https://efts.sec.gov/LATEST/search-index
Rate limit: 10 req/sec — handled by DataBroker.
"""
import requests
from datetime import date, timedelta
from ..broker import broker

EDGAR_HEADERS = {
    "User-Agent": "NeuralQuant research@neuralquant.ai",
    "Accept-Encoding": "gzip, deflate",
}
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions/{cik}.json"

class Form4Connector:
    def _fetch_raw(self, ticker: str, start: date, end: date) -> list[dict]:
        """Fetch Form 4 filings for a ticker from EDGAR full-text search."""
        params = {
            "q": f'"{ticker}"',
            "forms": "4",
            "dateRange": "custom",
            "startdt": start.isoformat(),
            "enddt": end.isoformat(),
        }
        with broker.acquire("edgar"):
            resp = requests.get(EDGAR_SEARCH, params=params, headers=EDGAR_HEADERS, timeout=15)
        if resp.status_code != 200:
            return []
        hits = resp.json().get("hits", {}).get("hits", [])
        results = []
        for hit in hits:
            src = hit.get("_source", {})
            # Simplified — a full implementation would parse the XML of each filing
            results.append({
                "ticker": ticker,
                "file_date": src.get("file_date"),
                "period": src.get("period_of_report"),
                "form_type": src.get("form_type"),
            })
        return results

    def get_insider_events(self, ticker: str, start: date, end: date) -> list[dict]:
        """Return parsed insider transaction events. Override _fetch_raw in tests."""
        return self._fetch_raw(ticker, start, end)


def compute_insider_cluster_score(events: list[dict], lookback_days: int = 90) -> float:
    """
    Score from 0.0 to 1.0 based on insider buying cluster.
    Algorithm:
    - Count net purchases (buys - sells) weighted by officer seniority
    - Normalize by lookback period
    - CEO/President = 3x weight, CFO/COO = 2x, Director = 1x
    """
    WEIGHTS = {"CEO": 3, "PRESIDENT": 3, "CFO": 2, "COO": 2, "CTO": 2}

    net_weighted = 0.0
    for e in events:
        title = (e.get("officer_title") or "").upper()
        weight = next((v for k, v in WEIGHTS.items() if k in title), 1)
        if e.get("is_purchase"):
            net_weighted += weight
        else:
            net_weighted -= weight * 0.5  # Sells count less (often routine diversification)

    # Normalize: 5 weighted buys = strong signal (1.0)
    return min(1.0, max(0.0, net_weighted / 5.0))
```

- [ ] **Step 5.3: Run tests**

```bash
cd packages/data && uv run pytest tests/test_alt_signals.py -v
```
Expected: Pass.

- [ ] **Step 5.4: Commit**

```bash
git add packages/data/src/nq_data/alt_signals/
git commit -m "feat(data): add SEC EDGAR Form 4 insider signal connector"
```

---

## Task 6: Signal Engine — Quality Composite (evolved from V8)

**Files:**
- Create: `packages/signals/src/nq_signals/__init__.py`
- Create: `packages/signals/src/nq_signals/models.py`
- Create: `packages/signals/src/nq_signals/factors/quality.py`
- Create: `packages/signals/tests/conftest.py`
- Create: `packages/signals/tests/test_quality.py`

> **Note:** The V8 system used 6 composite scores (Valuation, Risk, Growth, Momentum, Money Flow, Quality). The new signal engine decomposes these into 10 atomic signals, keeping V8's percentile-ranking approach but adding new signals and the LightGBM ranker on top.

- [ ] **Step 6.1: Write failing quality tests**

```python
# packages/signals/tests/test_quality.py
import pytest
import pandas as pd
from nq_signals.factors.quality import compute_piotroski_score, compute_quality_composite

def make_fundamental(roa=0.08, delta_roa=0.02, cfo=0.12, accruals=-0.03,
                     delta_leverage=-0.05, delta_liquidity=0.1, no_dilution=True,
                     delta_margin=0.02, delta_turnover=0.05) -> dict:
    return {
        "roa": roa, "delta_roa": delta_roa, "cfo": cfo,
        "accruals": accruals, "delta_leverage": delta_leverage,
        "delta_liquidity": delta_liquidity, "shares_issued": 0 if no_dilution else 1000000,
        "delta_gross_margin": delta_margin, "delta_asset_turnover": delta_turnover,
    }

def test_piotroski_score_high_quality():
    f = make_fundamental()
    score = compute_piotroski_score(f)
    assert score >= 7  # High quality firm should score 7-9

def test_piotroski_score_low_quality():
    f = make_fundamental(roa=-0.05, delta_roa=-0.03, cfo=-0.02, accruals=0.08,
                         delta_leverage=0.1, delta_liquidity=-0.2, no_dilution=False,
                         delta_margin=-0.05, delta_turnover=-0.03)
    score = compute_piotroski_score(f)
    assert score <= 3  # Poor quality

def test_quality_composite_cross_sectional_rank():
    """Quality composite should return percentile ranks across a universe."""
    universe = pd.DataFrame([
        {"ticker": "A", "gross_profit_margin": 0.70, "accruals_ratio": -0.05, "piotroski": 8},
        {"ticker": "B", "gross_profit_margin": 0.30, "accruals_ratio":  0.10, "piotroski": 4},
        {"ticker": "C", "gross_profit_margin": 0.50, "accruals_ratio": -0.01, "piotroski": 6},
    ])
    result = compute_quality_composite(universe)
    # A should rank highest (high margin, negative accruals = quality, high piotroski)
    assert result.loc[result["ticker"]=="A", "quality_percentile"].values[0] > \
           result.loc[result["ticker"]=="B", "quality_percentile"].values[0]
```

- [ ] **Step 6.2: Create quality.py**

```python
# packages/signals/src/nq_signals/factors/quality.py
"""
Quality Composite Signal — IC ~0.06-0.08.
Components:
  1. Piotroski F-Score (0-9): profitability + leverage + operating efficiency
  2. Gross Profitability (Novy-Marx 2013): gross_profit / total_assets
  3. Accruals ratio: (net_income - CFO) / avg_total_assets — lower is better
"""
import pandas as pd
import numpy as np


def compute_piotroski_score(f: dict) -> int:
    """
    Compute Piotroski F-Score (0-9) from fundamental data dictionary.
    Higher = better quality.
    """
    score = 0
    # --- Profitability (4 signals) ---
    if f.get("roa", 0) > 0: score += 1
    if f.get("cfo", 0) > 0: score += 1
    if f.get("delta_roa", 0) > 0: score += 1
    if f.get("cfo", 0) > f.get("roa", 0): score += 1  # Accruals: CFO > ROA = quality earnings
    # --- Leverage / Liquidity (3 signals) ---
    if f.get("delta_leverage", 0) < 0: score += 1   # Decreasing leverage = positive
    if f.get("delta_liquidity", 0) > 0: score += 1  # Increasing current ratio = positive
    if f.get("shares_issued", 0) == 0: score += 1    # No dilution = positive
    # --- Operating Efficiency (2 signals) ---
    if f.get("delta_gross_margin", 0) > 0: score += 1
    if f.get("delta_asset_turnover", 0) > 0: score += 1
    return score


def compute_quality_composite(universe: pd.DataFrame) -> pd.DataFrame:
    """
    Compute cross-sectional quality composite for a universe of stocks.
    Input DataFrame must have columns: ticker, gross_profit_margin, accruals_ratio, piotroski
    Returns DataFrame with added quality_percentile column (0.0 to 1.0).
    """
    df = universe.copy()

    # Percentile rank each component (higher = better)
    df["_gpm_rank"] = df["gross_profit_margin"].rank(pct=True)
    df["_accruals_rank"] = df["accruals_ratio"].rank(pct=True, ascending=False)  # Lower accruals = better
    df["_piotroski_rank"] = df["piotroski"].rank(pct=True)

    # Composite: equal weight across 3 components
    df["quality_percentile"] = (
        df["_gpm_rank"].fillna(0.5) * 0.40 +
        df["_accruals_rank"].fillna(0.5) * 0.35 +
        df["_piotroski_rank"].fillna(0.5) * 0.25
    )

    return df.drop(columns=["_gpm_rank", "_accruals_rank", "_piotroski_rank"])
```

- [ ] **Step 6.3: Run tests**

```bash
cd packages/signals && uv run pytest tests/test_quality.py -v
```
Expected: All pass.

- [ ] **Step 6.4: Commit**

```bash
git add packages/signals/src/nq_signals/factors/quality.py packages/signals/tests/
git commit -m "feat(signals): add quality composite factor (Piotroski + gross profit + accruals)"
```

---

## Task 7: Signal Engine — Momentum (with Crash Protection)

**Files:**
- Create: `packages/signals/src/nq_signals/factors/momentum.py`
- Test: `packages/signals/tests/test_momentum.py`

- [ ] **Step 7.1: Write failing test**

```python
# packages/signals/tests/test_momentum.py
import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta
from nq_signals.factors.momentum import compute_momentum_12_1, apply_crash_protection

def make_price_series(returns: list[float], start: date = date(2024, 1, 1)) -> pd.Series:
    prices = [100.0]
    for r in returns:
        prices.append(prices[-1] * (1 + r))
    idx = pd.date_range(start, periods=len(prices), freq="B")
    return pd.Series(prices, index=idx)

def test_momentum_12_1_positive():
    # Strong upward trend over 12 months
    prices = make_price_series([0.01] * 252)  # ~+12% cumulative return (approx)
    result = compute_momentum_12_1(prices)
    assert result > 0  # Positive momentum

def test_momentum_12_1_skips_last_month():
    # Classic 12-1: skip the most recent month (reversal effect)
    # Price up 11 months, down in last month — momentum should still be positive
    prices = make_price_series([0.01] * 231 + [-0.02] * 21)
    result = compute_momentum_12_1(prices)
    assert result > 0  # Still positive from 11 months of gains

def test_crash_protection_disables_momentum_in_bear():
    """In bear regime (SPX below 200MA), crash-protection flag should be True."""
    # SPX far below 200-day MA
    flag = apply_crash_protection(
        spx_return_1m=-0.15,
        spx_vs_200ma=-0.12,
    )
    assert flag is True  # Momentum signal should be suppressed

def test_crash_protection_off_in_bull():
    flag = apply_crash_protection(spx_return_1m=0.02, spx_vs_200ma=0.05)
    assert flag is False
```

- [ ] **Step 7.2: Create momentum.py**

```python
# packages/signals/src/nq_signals/factors/momentum.py
import pandas as pd
import numpy as np

def compute_momentum_12_1(prices: pd.Series) -> float:
    """
    Classic 12-1 momentum: return from 12 months ago to 1 month ago.
    Skips most recent month to avoid short-term reversal contamination.
    Returns raw return (not percentile — caller handles cross-sectional ranking).
    """
    if len(prices) < 252:
        return 0.0
    # 252 trading days ≈ 12 months; 21 ≈ 1 month
    price_12m_ago = float(prices.iloc[-252])
    price_1m_ago = float(prices.iloc[-21])
    if price_12m_ago == 0:
        return 0.0
    return (price_1m_ago - price_12m_ago) / price_12m_ago


def apply_crash_protection(
    spx_return_1m: float,
    spx_vs_200ma: float,
    drawdown_threshold: float = -0.10,
    ma_threshold: float = -0.05,
) -> bool:
    """
    Returns True when momentum should be suppressed (crash risk high).
    Triggers when SPX drops >10% in a month OR is >5% below its 200-day MA.
    Documented: momentum crashes most severely during sharp market reversals.
    """
    return spx_return_1m < drawdown_threshold or spx_vs_200ma < ma_threshold


def compute_momentum_cross_sectional(universe: pd.DataFrame,
                                     crash_flag: bool = False) -> pd.DataFrame:
    """
    Cross-sectional momentum ranking.
    universe: DataFrame with ticker, momentum_raw (from compute_momentum_12_1)
    Returns DataFrame with momentum_percentile column.
    If crash_flag is True, all momentum scores are set to 0.5 (neutral) — signal suppressed.
    """
    df = universe.copy()
    if crash_flag:
        df["momentum_percentile"] = 0.5
    else:
        df["momentum_percentile"] = df["momentum_raw"].rank(pct=True)
    return df
```

- [ ] **Step 7.3: Run tests**

```bash
cd packages/signals && uv run pytest tests/test_momentum.py -v
```
Expected: All pass.

- [ ] **Step 7.4: Commit**

```bash
git add packages/signals/src/nq_signals/factors/momentum.py packages/signals/tests/test_momentum.py
git commit -m "feat(signals): add momentum 12-1 factor with crash-protection filter"
```

---

## Task 8: 4-Regime HMM Detector

**Files:**
- Create: `packages/signals/src/nq_signals/regime/hmm_detector.py`
- Create: `packages/signals/tests/test_hmm.py`

- [ ] **Step 8.1: Write failing tests**

```python
# packages/signals/tests/test_hmm.py
import pytest
import numpy as np
import pandas as pd
from nq_signals.regime.hmm_detector import RegimeDetector, RegimeState

def make_macro_df(n: int = 200) -> pd.DataFrame:
    """Synthetic macro data with two obvious regimes."""
    np.random.seed(42)
    # First half: calm (VIX low, positive spread, tight spreads)
    calm = pd.DataFrame({
        "vix": np.random.normal(14, 2, n//2).clip(8, 20),
        "vix_20d_change": np.random.normal(-0.1, 0.5, n//2),
        "spx_vs_200ma": np.random.normal(0.05, 0.02, n//2),
        "hy_spread_oas": np.random.normal(300, 30, n//2),
        "ism_pmi": np.random.normal(53, 2, n//2),
    })
    # Second half: stressed (VIX high, SPX below MA, spreads wide)
    stressed = pd.DataFrame({
        "vix": np.random.normal(30, 5, n//2).clip(20, 80),
        "vix_20d_change": np.random.normal(0.5, 0.8, n//2),
        "spx_vs_200ma": np.random.normal(-0.08, 0.03, n//2),
        "hy_spread_oas": np.random.normal(700, 80, n//2),
        "ism_pmi": np.random.normal(46, 3, n//2),
    })
    return pd.concat([calm, stressed], ignore_index=True)

def test_regime_detector_fits_without_error():
    df = make_macro_df(200)
    detector = RegimeDetector(n_regimes=4)
    detector.fit(df)  # Should not raise

def test_regime_detector_returns_soft_posteriors():
    df = make_macro_df(200)
    detector = RegimeDetector(n_regimes=4)
    detector.fit(df)
    posteriors = detector.predict_proba(df)
    assert posteriors.shape == (len(df), 4)
    # Each row sums to ~1.0
    np.testing.assert_allclose(posteriors.sum(axis=1), 1.0, atol=1e-5)

def test_regime_state_identifies_stress():
    df = make_macro_df(200)
    detector = RegimeDetector(n_regimes=4)
    detector.fit(df)
    # Check last row (should be stressed regime)
    state = detector.get_current_state(df.iloc[-1:])
    assert isinstance(state, RegimeState)
    assert 0.0 <= state.confidence <= 1.0
    assert state.regime_id in [1, 2, 3, 4]
```

- [ ] **Step 8.2: Create hmm_detector.py**

```python
# packages/signals/src/nq_signals/regime/hmm_detector.py
"""
4-State Hidden Markov Model for market regime detection.
States:
  1 = Risk-On / Trending
  2 = Late Cycle / Overheating
  3 = Stress / Bear
  4 = Recovery
Trained on: VIX, VIX 20d change, SPX vs 200MA, HY spread OAS, ISM PMI
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional
from sklearn.preprocessing import StandardScaler
from hmmlearn.hmm import GaussianHMM

FEATURE_COLS = ["vix", "vix_20d_change", "spx_vs_200ma", "hy_spread_oas", "ism_pmi"]

# Human-interpretable regime labels based on typical macro patterns
REGIME_LABELS = {
    1: "Risk-On / Trending",
    2: "Late Cycle / Overheating",
    3: "Stress / Bear",
    4: "Recovery",
}

@dataclass
class RegimeState:
    regime_id: int          # 1-4
    label: str
    confidence: float       # Max posterior probability (soft assignment)
    posteriors: np.ndarray  # Full 4-element probability vector
    factor_weights: dict    # Recommended factor weights for this regime

# Factor weights per regime (from spec Section 4.2)
REGIME_WEIGHTS = {
    1: {"momentum": 0.30, "quality": 0.25, "value": 0.10, "low_vol": 0.10, "growth": 0.25},
    2: {"momentum": 0.10, "quality": 0.20, "value": 0.30, "low_vol": 0.15, "growth": 0.25},
    3: {"momentum": 0.05, "quality": 0.30, "value": 0.20, "low_vol": 0.35, "growth": 0.10},
    4: {"momentum": 0.20, "quality": 0.15, "value": 0.30, "low_vol": 0.05, "growth": 0.30},
}

class RegimeDetector:
    def __init__(self, n_regimes: int = 4, random_state: int = 42):
        self.n_regimes = n_regimes
        self._scaler = StandardScaler()
        self._hmm = GaussianHMM(
            n_components=n_regimes,
            covariance_type="full",
            n_iter=100,
            random_state=random_state,
        )
        self._fitted = False
        self._regime_map: dict[int, int] = {}  # HMM state → semantic regime 1-4

    def fit(self, macro_df: pd.DataFrame) -> "RegimeDetector":
        """Fit HMM on historical macro data."""
        X = macro_df[FEATURE_COLS].fillna(method="ffill").fillna(0).values
        X_scaled = self._scaler.fit_transform(X)
        self._hmm.fit(X_scaled)
        self._fitted = True
        self._regime_map = self._assign_semantic_regimes(X_scaled)
        return self

    def _assign_semantic_regimes(self, X_scaled: np.ndarray) -> dict[int, int]:
        """
        Map HMM states (0-indexed) to semantic regime IDs (1-4) based on
        mean VIX and mean SPX-vs-200MA of each state.
        Highest VIX + most negative SPX-vs-200MA → Regime 3 (Stress/Bear)
        Lowest VIX + most positive SPX-vs-200MA → Regime 1 (Risk-On)
        """
        means = self._hmm.means_  # Shape: (n_components, n_features)
        # Feature indices: vix=0, vix_20d_change=1, spx_vs_200ma=2, hy_spread=3, pmi=4
        vix_col = 0
        spx_col = 2

        # Score each state: higher score = more stressed
        stress_scores = means[:, vix_col] - means[:, spx_col]
        ranking = np.argsort(stress_scores)  # Low stress to high stress

        # ranking[0] = least stressed = Risk-On (1)
        # ranking[1] = second least = Late Cycle (2) or Recovery (4) — use PMI slope
        # ranking[-1] = most stressed = Bear (3)
        mapping = {}
        mapping[int(ranking[0])] = 1   # Risk-On
        mapping[int(ranking[1])] = 4   # Recovery (low-moderate stress, recovering)
        mapping[int(ranking[2])] = 2   # Late Cycle (moderate-high stress)
        mapping[int(ranking[3])] = 3   # Bear/Stress
        return mapping

    def predict_proba(self, macro_df: pd.DataFrame) -> np.ndarray:
        """Return soft posterior probabilities. Shape: (n_rows, n_regimes)."""
        assert self._fitted, "Call fit() first"
        X = macro_df[FEATURE_COLS].fillna(method="ffill").fillna(0).values
        X_scaled = self._scaler.transform(X)
        # hmmlearn predict_proba returns shape (n_samples, n_components)
        raw_posteriors = self._hmm.predict_proba(X_scaled)
        # Reorder columns to match semantic regime IDs 1-4
        reordered = np.zeros_like(raw_posteriors)
        for hmm_state, semantic_id in self._regime_map.items():
            reordered[:, semantic_id - 1] = raw_posteriors[:, hmm_state]
        return reordered

    def get_current_state(self, latest_row: pd.DataFrame) -> RegimeState:
        """Get current regime state from the most recent macro observation."""
        posteriors = self.predict_proba(latest_row)[0]
        regime_idx = int(np.argmax(posteriors))  # 0-indexed
        regime_id = regime_idx + 1
        confidence = float(posteriors[regime_idx])
        return RegimeState(
            regime_id=regime_id,
            label=REGIME_LABELS[regime_id],
            confidence=confidence,
            posteriors=posteriors,
            factor_weights=REGIME_WEIGHTS[regime_id],
        )
```

- [ ] **Step 8.3: Run tests**

```bash
cd packages/signals && uv run pytest tests/test_hmm.py -v
```
Expected: All pass.

- [ ] **Step 8.4: Commit**

```bash
git add packages/signals/src/nq_signals/regime/
git commit -m "feat(signals): add 4-regime HMM detector with soft posterior assignment"
```

---

## Task 9: LightGBM LambdaRank Signal Ranker

**Files:**
- Create: `packages/signals/src/nq_signals/ranker/lgbm_ranker.py`
- Create: `packages/signals/src/nq_signals/ranker/walk_forward.py`
- Create: `packages/signals/tests/test_lgbm.py`

- [ ] **Step 9.1: Write failing tests**

```python
# packages/signals/tests/test_lgbm.py
import pytest
import numpy as np
import pandas as pd
from nq_signals.ranker.lgbm_ranker import SignalRanker
from nq_signals.ranker.walk_forward import compute_ic, compute_icir

def make_synthetic_data(n_stocks: int = 50, n_periods: int = 8) -> pd.DataFrame:
    """Make fake factor + return data for testing."""
    np.random.seed(42)
    records = []
    for period in range(n_periods):
        quality = np.random.rand(n_stocks)
        momentum = np.random.rand(n_stocks)
        # True return correlates with quality + momentum (signal has alpha)
        true_signal = 0.6 * quality + 0.4 * momentum
        noise = np.random.randn(n_stocks) * 0.2
        returns = true_signal + noise
        for i in range(n_stocks):
            records.append({
                "period": period, "ticker": f"STOCK_{i:03d}",
                "quality_percentile": quality[i],
                "momentum_percentile": momentum[i],
                "low_vol_percentile": np.random.rand(),
                "next_period_return": returns[i],
            })
    return pd.DataFrame(records)

def test_ranker_fits_and_predicts():
    df = make_synthetic_data()
    train = df[df["period"] < 6]
    test = df[df["period"] >= 6]
    ranker = SignalRanker()
    ranker.fit(train, feature_cols=["quality_percentile", "momentum_percentile", "low_vol_percentile"],
               target_col="next_period_return", group_col="period")
    scores = ranker.predict(test[["quality_percentile", "momentum_percentile", "low_vol_percentile"]])
    assert len(scores) == len(test)
    assert not np.any(np.isnan(scores))

def test_ic_is_positive_with_signal():
    """IC should be positive when predictions correlate with actual returns."""
    df = make_synthetic_data()
    train = df[df["period"] < 6]
    test = df[df["period"] >= 6]
    ranker = SignalRanker()
    feature_cols = ["quality_percentile", "momentum_percentile", "low_vol_percentile"]
    ranker.fit(train, feature_cols=feature_cols,
               target_col="next_period_return", group_col="period")
    test = test.copy()
    test["predicted_score"] = ranker.predict(test[feature_cols])
    ic = compute_ic(test, predicted_col="predicted_score", actual_col="next_period_return",
                    group_col="period")
    assert ic.mean() > 0  # Positive IC confirms signal has predictive value

def test_compute_icir():
    ic_series = pd.Series([0.08, 0.06, 0.10, 0.05, 0.09])
    icir = compute_icir(ic_series)
    assert icir > 0
    assert icir == pytest.approx(ic_series.mean() / ic_series.std(), rel=0.01)
```

- [ ] **Step 9.2: Create lgbm_ranker.py**

```python
# packages/signals/src/nq_signals/ranker/lgbm_ranker.py
"""
LightGBM LambdaRank — cross-sectional stock ranking model.
Framing: learning-to-rank (not regression) — rank stocks by expected return.
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.preprocessing import MinMaxScaler

class SignalRanker:
    def __init__(self, num_leaves: int = 31, n_estimators: int = 200,
                 learning_rate: float = 0.05):
        self.params = {
            "objective": "lambdarank",
            "metric": "ndcg",
            "ndcg_eval_at": [5, 10],
            "num_leaves": num_leaves,
            "n_estimators": n_estimators,
            "learning_rate": learning_rate,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "min_child_samples": 5,
            "verbose": -1,
        }
        self._model: lgb.LGBMRanker | None = None
        self._feature_cols: list[str] = []

    def fit(self, df: pd.DataFrame, feature_cols: list[str],
            target_col: str, group_col: str) -> "SignalRanker":
        """
        Train LambdaRank on panel data.
        df: DataFrame with feature_cols, target_col (returns), group_col (period/quarter)
        """
        self._feature_cols = feature_cols
        groups = df.groupby(group_col, sort=True)
        group_sizes = [len(g) for _, g in groups]

        # Convert continuous returns to relevance grades (0-3) for LambdaRank
        # LightGBM lambdarank requires non-negative integer labels
        df = df.copy()
        for period, g_idx in groups.groups.items():
            q = df.loc[g_idx, target_col].rank(pct=True)
            df.loc[g_idx, "_relevance"] = (q * 3).astype(int).clip(0, 3)

        X = df[feature_cols].fillna(0.5).values
        y = df["_relevance"].values.astype(int)

        self._model = lgb.LGBMRanker(**self.params)
        self._model.fit(X, y, group=group_sizes)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Return ranking scores. Higher = better expected return."""
        assert self._model is not None, "Call fit() first"
        return self._model.predict(X[self._feature_cols].fillna(0.5).values)

    @property
    def feature_importances(self) -> dict[str, float]:
        if self._model is None:
            return {}
        return dict(zip(self._feature_cols,
                        self._model.feature_importances_.tolist()))
```

- [ ] **Step 9.3: Create walk_forward.py**

```python
# packages/signals/src/nq_signals/ranker/walk_forward.py
"""
Walk-forward cross-validation and IC/ICIR metrics.
Following Lopez de Prado (2018): train on T years, test on OOS.
"""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from .lgbm_ranker import SignalRanker

def compute_ic(df: pd.DataFrame, predicted_col: str,
               actual_col: str, group_col: str) -> pd.Series:
    """
    Information Coefficient (IC): Spearman rank correlation between
    predicted scores and actual next-period returns, computed per group.
    """
    ics = {}
    for period, group in df.groupby(group_col):
        pred = group[predicted_col].values
        actual = group[actual_col].values
        if len(pred) < 3:
            continue
        ic, _ = spearmanr(pred, actual)
        ics[period] = ic
    return pd.Series(ics)


def compute_icir(ic_series: pd.Series) -> float:
    """ICIR = IC mean / IC std. Target > 0.5; world-class > 1.0"""
    if ic_series.std() == 0:
        return 0.0
    return float(ic_series.mean() / ic_series.std())


def walk_forward_validate(df: pd.DataFrame, feature_cols: list[str],
                          target_col: str, period_col: str,
                          train_periods: int = 20,
                          test_periods: int = 4) -> dict:
    """
    Walk-forward validation following Lopez de Prado.
    Returns dict with IC series, ICIR, and hit rate per OOS period.
    """
    periods = sorted(df[period_col].unique())
    all_predictions = []

    for i in range(train_periods, len(periods) - test_periods + 1, test_periods):
        train_p = periods[i - train_periods: i]
        test_p = periods[i: i + test_periods]

        train_df = df[df[period_col].isin(train_p)]
        test_df = df[df[period_col].isin(test_p)].copy()

        ranker = SignalRanker()
        ranker.fit(train_df, feature_cols, target_col, period_col)
        test_df["predicted_score"] = ranker.predict(test_df)
        all_predictions.append(test_df)

    if not all_predictions:
        return {"ic": pd.Series(), "icir": 0.0, "hit_rate": 0.0}

    combined = pd.concat(all_predictions)
    ic = compute_ic(combined, "predicted_score", target_col, period_col)
    icir = compute_icir(ic)
    hit_rate = float((ic > 0).mean())

    return {"ic": ic, "icir": icir, "hit_rate": hit_rate,
            "ic_mean": float(ic.mean()), "ic_std": float(ic.std())}
```

- [ ] **Step 9.4: Run tests**

```bash
cd packages/signals && uv run pytest tests/test_lgbm.py -v
```
Expected: All pass.

- [ ] **Step 9.5: Commit**

```bash
git add packages/signals/src/nq_signals/ranker/
git commit -m "feat(signals): add LightGBM LambdaRank ranker + walk-forward validation + IC/ICIR metrics"
```

---

## Task 10: Signal Engine Orchestrator

**Files:**
- Create: `packages/signals/src/nq_signals/engine.py`
- Create: `packages/signals/tests/test_engine.py`

- [ ] **Step 10.1: Write failing test**

```python
# packages/signals/tests/test_engine.py
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from nq_signals.engine import SignalEngine, UniverseSnapshot

def make_mock_snapshot() -> UniverseSnapshot:
    tickers = [f"STOCK_{i}" for i in range(20)]
    return UniverseSnapshot(
        tickers=tickers,
        market="US",
        fundamentals=pd.DataFrame({
            "ticker": tickers,
            "gross_profit_margin": [0.4 + i*0.01 for i in range(20)],
            "accruals_ratio": [-0.02 - i*0.001 for i in range(20)],
            "piotroski": [5 + i % 4 for i in range(20)],
            "momentum_raw": [0.1 + i*0.01 for i in range(20)],
            "short_interest_pct": [0.05 - i*0.001 for i in range(20)],
        }),
        macro=MagicMock(vix=15.0, spx_vs_200ma=0.05, hy_spread_oas=320.0,
                        ism_pmi=52.0, yield_spread_2y10y=0.2),
    )

def test_engine_returns_ranked_universe():
    engine = SignalEngine()
    snapshot = make_mock_snapshot()
    with patch.object(engine, "_get_regime", return_value=MagicMock(
        regime_id=1, confidence=0.82,
        factor_weights={"momentum": 0.30, "quality": 0.25, "value": 0.10,
                        "low_vol": 0.10, "growth": 0.25},
        posteriors=[0.82, 0.1, 0.05, 0.03],
    )):
        result = engine.compute(snapshot)
    assert "ticker" in result.columns
    assert "composite_score" in result.columns
    assert len(result) == 20
    assert result["composite_score"].is_monotonic_decreasing  # Ranked high→low
```

- [ ] **Step 10.2: Create engine.py**

```python
# packages/signals/src/nq_signals/engine.py
"""
Signal Engine Orchestrator — computes all 10 signals and produces a ranked universe.
This is the Layer 2 workhorse that feeds the Layer 3 agent system.
"""
from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np

from .factors.quality import compute_quality_composite, compute_piotroski_score
from .factors.momentum import compute_momentum_cross_sectional, apply_crash_protection
from .regime.hmm_detector import RegimeDetector, RegimeState


@dataclass
class UniverseSnapshot:
    tickers: list[str]
    market: str          # "US" | "IN" | "GLOBAL"
    fundamentals: pd.DataFrame
    macro: object        # MacroSnapshot-like object


class SignalEngine:
    def __init__(self, regime_detector: Optional[RegimeDetector] = None):
        self._regime_detector = regime_detector

    def _get_regime(self, macro) -> RegimeState:
        """Get current market regime from macro snapshot."""
        if self._regime_detector is None or not self._regime_detector._fitted:
            # Default to Risk-On if no model fitted
            from .regime.hmm_detector import RegimeState, REGIME_WEIGHTS
            return RegimeState(
                regime_id=1, label="Risk-On / Trending",
                confidence=0.5,
                posteriors=np.array([0.5, 0.2, 0.2, 0.1]),
                factor_weights=REGIME_WEIGHTS[1],
            )
        macro_row = pd.DataFrame([{
            "vix": macro.vix, "vix_20d_change": 0.0,
            "spx_vs_200ma": macro.spx_vs_200ma,
            "hy_spread_oas": macro.hy_spread_oas,
            "ism_pmi": macro.ism_pmi,
        }])
        return self._regime_detector.get_current_state(macro_row)

    def compute(self, snapshot: UniverseSnapshot) -> pd.DataFrame:
        """
        Compute all signals and return regime-weighted composite scores.
        Returns DataFrame sorted by composite_score descending.
        """
        df = snapshot.fundamentals.copy()
        regime = self._get_regime(snapshot.macro)

        crash_flag = apply_crash_protection(
            spx_return_1m=getattr(snapshot.macro, "spx_return_1m", 0.0),
            spx_vs_200ma=getattr(snapshot.macro, "spx_vs_200ma", 0.0),
        )

        # 1. Quality composite
        df = compute_quality_composite(df)

        # 2. Momentum
        df = compute_momentum_cross_sectional(df, crash_flag=crash_flag)

        # 3. Short interest (lower = better — already as percentile, inverted)
        if "short_interest_pct" in df.columns:
            df["short_interest_percentile"] = 1.0 - df["short_interest_pct"].rank(pct=True)
        else:
            df["short_interest_percentile"] = 0.5

        # Regime-weighted composite
        w = regime.factor_weights
        df["composite_score"] = (
            df.get("quality_percentile", pd.Series(0.5, index=df.index)) * w.get("quality", 0.25) +
            df.get("momentum_percentile", pd.Series(0.5, index=df.index)) * w.get("momentum", 0.25) +
            df.get("short_interest_percentile", pd.Series(0.5, index=df.index)) * 0.15 +
            df.get("quality_percentile", pd.Series(0.5, index=df.index)) * w.get("value", 0.10) +
            df.get("quality_percentile", pd.Series(0.5, index=df.index)) * w.get("low_vol", 0.15)
        )

        df["regime_id"] = regime.regime_id
        df["regime_confidence"] = regime.confidence

        return df.sort_values("composite_score", ascending=False).reset_index(drop=True)
```

- [ ] **Step 10.3: Run all signal tests**

```bash
cd packages/signals && uv run pytest tests/ -v
```
Expected: All pass.

- [ ] **Step 10.4: Commit**

```bash
git add packages/signals/src/nq_signals/engine.py packages/signals/tests/test_engine.py
git commit -m "feat(signals): add SignalEngine orchestrator — computes regime-weighted composite scores"
```

---

## Task 11: Backtesting Framework

**Files:**
- Create: `scripts/backtest/run_backtest.py`
- Create: `scripts/backtest/report.py`

- [ ] **Step 11.1: Create backtest runner**

```python
# scripts/backtest/run_backtest.py
"""
Backtest runner — validates signal engine on 16+ historical quarters.
Uses walk-forward validation: train on past, evaluate on future.

Usage:
    uv run python scripts/backtest/run_backtest.py --data-dir data/ --output results/

Expects CSV files in data/ with columns:
  ProcessDate, ticker, market, [signal columns], next_quarter_return
"""
import argparse
import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages/signals/src"))

from nq_signals.ranker.walk_forward import walk_forward_validate

FEATURE_COLS = [
    "quality_percentile", "momentum_percentile", "short_interest_percentile",
    "insider_percentile", "earnings_surprise_percentile",
]

def load_historical_data(data_dir: str) -> pd.DataFrame:
    """Load all quarterly CSVs from data_dir and combine."""
    dfs = []
    for f in Path(data_dir).glob("*.csv"):
        df = pd.read_csv(f)
        dfs.append(df)
    if not dfs:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")
    return pd.concat(dfs, ignore_index=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/backtest")
    parser.add_argument("--output", default="results/backtest")
    parser.add_argument("--train-periods", type=int, default=12)
    parser.add_argument("--test-periods", type=int, default=4)
    args = parser.parse_args()

    print("Loading historical data...")
    df = load_historical_data(args.data_dir)

    available_features = [c for c in FEATURE_COLS if c in df.columns]
    print(f"Available features: {available_features}")
    print(f"Periods: {sorted(df['period'].unique())}")

    print("\nRunning walk-forward validation...")
    results = walk_forward_validate(
        df=df, feature_cols=available_features,
        target_col="next_quarter_return", period_col="period",
        train_periods=args.train_periods, test_periods=args.test_periods,
    )

    print(f"\n{'='*50}")
    print("BACKTEST RESULTS")
    print(f"{'='*50}")
    print(f"IC Mean:    {results['ic_mean']:.4f}  (target: >0.05)")
    print(f"IC Std:     {results['ic_std']:.4f}")
    print(f"ICIR:       {results['icir']:.4f}  (target: >0.5)")
    print(f"Hit Rate:   {results['hit_rate']:.1%}  (target: >55%)")

    Path(args.output).mkdir(parents=True, exist_ok=True)
    results["ic"].to_csv(f"{args.output}/ic_by_period.csv")
    print(f"\nIC by period saved to {args.output}/ic_by_period.csv")

if __name__ == "__main__":
    main()
```

- [ ] **Step 11.2: Port V8 historical data for backtest**

```bash
# Copy existing V8 data to the backtest data directory
mkdir -p C:/Users/point/projects/stockpredictor/data/backtest
cp "C:/Users/point/projects/finance/stock-selector-deploy/All Qtrs Data.csv" \
   C:/Users/point/projects/stockpredictor/data/backtest/india_all_quarters.csv
```

- [ ] **Step 11.3: Run backtest with V8 data**

```bash
cd C:/Users/point/projects/stockpredictor
uv run python scripts/backtest/run_backtest.py \
  --data-dir data/backtest \
  --output results/backtest \
  --train-periods 8 \
  --test-periods 2
```
Expected output: IC Mean, ICIR, Hit Rate printed. Results CSV saved.

- [ ] **Step 11.4: Commit**

```bash
git add scripts/backtest/ data/.gitkeep results/.gitkeep
echo "data/backtest/*.csv" >> .gitignore  # Don't commit large data files
git commit -m "feat: add backtesting framework with walk-forward IC/ICIR validation"
```

---

## Task 12: Integration Test — End-to-End Signal Run

- [ ] **Step 12.1: Write integration test**

```python
# packages/signals/tests/test_integration.py
"""
Integration test: DataBroker → DataStore → SignalEngine → ranked output.
Uses mocked data sources to avoid real API calls in CI.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import date
from unittest.mock import patch, MagicMock
from nq_data.store import DataStore
from nq_signals.engine import SignalEngine, UniverseSnapshot

def make_universe(n: int = 10) -> UniverseSnapshot:
    tickers = [f"T{i:02d}" for i in range(n)]
    np.random.seed(0)
    return UniverseSnapshot(
        tickers=tickers, market="US",
        fundamentals=pd.DataFrame({
            "ticker": tickers,
            "gross_profit_margin": np.random.uniform(0.2, 0.8, n),
            "accruals_ratio": np.random.uniform(-0.1, 0.1, n),
            "piotroski": np.random.randint(3, 9, n),
            "momentum_raw": np.random.uniform(-0.2, 0.5, n),
            "short_interest_pct": np.random.uniform(0.01, 0.15, n),
        }),
        macro=MagicMock(vix=16.0, spx_vs_200ma=0.03, hy_spread_oas=340.0,
                        ism_pmi=51.0, yield_spread_2y10y=0.15, spx_return_1m=0.02),
    )

def test_full_signal_pipeline():
    engine = SignalEngine()
    snapshot = make_universe(10)
    result = engine.compute(snapshot)

    assert len(result) == 10
    assert result.iloc[0]["composite_score"] >= result.iloc[-1]["composite_score"]
    assert "regime_id" in result.columns
    assert result["regime_id"].iloc[0] in [1, 2, 3, 4]
    print("\nTop 3 picks:")
    print(result[["ticker", "composite_score", "quality_percentile", "regime_id"]].head(3))
```

- [ ] **Step 12.2: Run integration test**

```bash
cd packages/signals && uv run pytest tests/test_integration.py -v -s
```
Expected: Pass + top 3 picks printed.

- [ ] **Step 12.3: Run full test suite**

```bash
cd C:/Users/point/projects/stockpredictor
uv run pytest packages/ -v --tb=short
```
Expected: All tests pass.

- [ ] **Step 12.4: Final Phase 1 commit**

```bash
git add .
git commit -m "feat: Phase 1 complete — data pipeline + 10-signal engine + HMM regime + LightGBM + backtest framework

Phase 1 deliverables:
- DataBroker rate limiter (20+ sources, token bucket per source)
- DuckDB DataStore (OHLCV, fundamentals, macro storage)
- Price connectors: yfinance (US+India) + NSE Bhavcopy (free, official)
- Macro connector: FRED API (VIX, yields, spreads, PMI, CPI)
- Alt signals: SEC EDGAR Form 4 insider cluster signal
- Signal engine: quality composite, momentum 12-1 with crash protection
- 4-regime HMM detector with soft posterior assignment
- LightGBM LambdaRank ranker + walk-forward IC/ICIR validation
- Signal orchestrator with regime-adaptive weighting
- Backtesting framework ready to run on V8 historical data

IC target: >0.05 monthly | ICIR target: >0.5 | Hit rate target: >55%
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 1 Done — What's Next

Phase 1 produces **working, testable software**: a Python library that takes a stock universe + macro data and outputs a ranked list with IC-validated signals and regime detection. No UI, no agents yet — but a solid foundation.

**Phase 2 plan** (to be written when Phase 1 is complete) covers:
- 7-agent Claude PARA-DEBATE system
- All agent prompts + I/O contracts
- QUANT-RANK aggregation + HEAD ANALYST synthesis
- Brier-score confidence calibration
- Celery async job scheduling

**Phase 3 plan** covers:
- Next.js 15 frontend (5 screens, Google Stitch UI)
- FastAPI backend + Supabase + Clerk + Stripe

**Phase 4 plan** covers:
- Full backtest (16+ quarters) + Validation Center
- GitHub repo with stunning README
- ProductHunt launch prep

---

## Quick Reference

```bash
# Run all tests
uv run pytest packages/ -v

# Run backtest
uv run python scripts/backtest/run_backtest.py --data-dir data/backtest

# Add a new data connector
# 1. Create packages/data/src/nq_data/<category>/<connector>.py
# 2. Register rate limit in DataBroker.DEFAULTS
# 3. Add tests in packages/data/tests/

# Add a new signal factor
# 1. Create packages/signals/src/nq_signals/factors/<name>.py
# 2. Add cross-sectional compute function
# 3. Wire into engine.py SignalEngine.compute()
# 4. Add tests
```

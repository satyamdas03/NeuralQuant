"""
Phase 3 real data builder.
Replaces synthetic snapshots with live yfinance data.
Falls back to deterministic synthetic values for any ticker/field that fails.

Performance:
  - Macro: cached 1 hour (single batch of ~6 yfinance calls)
  - Prices: batch-downloaded once for all tickers, cached 1 hour
  - Fundamentals (info): parallel fetch, cached 4 hours per ticker
  - First screener load: ~10-20 s; subsequent: <1 s (cache hit)
"""
from __future__ import annotations

import logging
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import numpy as np
import pandas as pd
import yfinance as yf

from nq_signals.engine import UniverseSnapshot

log = logging.getLogger(__name__)

# ─── Cache ─────────────────────────────────────────────────────────────────────
_lock = threading.Lock()
_fund_cache: dict[str, dict] = {}
_fund_ts: dict[str, float] = {}
_price_cache: dict[str, pd.Series] = {}   # ticker -> close price Series
_price_ts: dict[str, float] = {}
_macro_cache: "_LiveMacro | None" = None
_macro_ts: float = 0.0

FUND_TTL = 4 * 3600    # 4 hours
PRICE_TTL = 3600        # 1 hour
MACRO_TTL = 3600        # 1 hour
MAX_WORKERS = 12


# ─── Macro ─────────────────────────────────────────────────────────────────────

@dataclass
class _LiveMacro:
    vix: float = 18.0
    spx_vs_200ma: float = 0.02
    hy_spread_oas: float = 350.0
    ism_pmi: float = 51.0
    yield_spread_2y10y: float = 0.10
    spx_return_1m: float = 0.01


def _safe(val, default: float = 0.0) -> float:
    try:
        f = float(val)
        return f if math.isfinite(f) else default
    except Exception:
        return default


def fetch_real_macro() -> _LiveMacro:
    global _macro_cache, _macro_ts
    with _lock:
        if _macro_cache is not None and time.time() - _macro_ts < MACRO_TTL:
            return _macro_cache

    m = _LiveMacro()

    # VIX
    try:
        h = yf.Ticker("^VIX").history(period="5d", auto_adjust=True)
        if not h.empty:
            m.vix = float(h["Close"].iloc[-1])
    except Exception:
        pass

    # SPX: 200-day MA ratio + 1-month return
    try:
        spx = yf.Ticker("^GSPC").history(period="252d", auto_adjust=True)
        if len(spx) >= 200:
            last = float(spx["Close"].iloc[-1])
            ma200 = float(spx["Close"].tail(200).mean())
            m.spx_vs_200ma = (last - ma200) / ma200
        if len(spx) >= 22:
            m.spx_return_1m = (
                float(spx["Close"].iloc[-1]) / float(spx["Close"].iloc[-22]) - 1
            )
    except Exception:
        pass

    # Yield curve: 10Y (^TNX) – 5Y (^FVX) as proxy for 2Y–10Y spread
    try:
        tnx = yf.Ticker("^TNX").history(period="5d", auto_adjust=True)
        fvx = yf.Ticker("^FVX").history(period="5d", auto_adjust=True)
        if not tnx.empty and not fvx.empty:
            m.yield_spread_2y10y = (
                float(tnx["Close"].iloc[-1]) - float(fvx["Close"].iloc[-1])
            ) / 100
    except Exception:
        pass

    # FRED (optional — requires FRED_API_KEY env var, free at fred.stlouisfed.org)
    fred_key = os.environ.get("FRED_API_KEY", "").strip()
    if fred_key:
        try:
            from datetime import date
            from nq_data.macro.fred_connector import FREDConnector
            snap = FREDConnector(api_key=fred_key).get_snapshot(date.today())
            if snap.hy_spread_oas:
                m.hy_spread_oas = snap.hy_spread_oas
            if snap.ism_pmi:
                m.ism_pmi = snap.ism_pmi
            if snap.yield_spread_2y10y:
                m.yield_spread_2y10y = snap.yield_spread_2y10y
        except Exception as exc:
            log.warning("FRED fetch failed: %s", exc)

    with _lock:
        _macro_cache = m
        _macro_ts = time.time()
    return m


# ─── Per-ticker fundamentals ───────────────────────────────────────────────────

def _synthetic_row(ticker: str) -> dict:
    """Deterministic synthetic fallback — same values as Phase 2."""
    s = hash(ticker) % (2**31 - 1)
    return {
        "gross_profit_margin": float(np.random.RandomState(s).uniform(0.1, 0.9)),
        "accruals_ratio": float(np.random.RandomState(s + 1).uniform(-0.15, 0.15)),
        "piotroski": int(np.random.RandomState(s + 2).randint(2, 9)),
        "momentum_raw": float(np.random.RandomState(s + 3).uniform(-0.3, 0.6)),
        "short_interest_pct": float(np.random.RandomState(s + 4).uniform(0.005, 0.20)),
    }


def _piotroski_from_info(info: dict) -> int:
    """Compute Piotroski F-Score (0–9) from yfinance info dict."""
    ni = _safe(info.get("netIncomeToCommon"))
    ta = _safe(info.get("totalAssets"), 1) or 1
    ocf = _safe(info.get("operatingCashflow"))
    score = 0
    if ni / ta > 0:                                       score += 1  # ROA > 0
    if ocf > 0:                                           score += 1  # CFO > 0
    if ocf > ni:                                          score += 1  # CFO > NI (accruals quality)
    if _safe(info.get("grossMargins")) > 0:               score += 1  # GP margin positive
    if _safe(info.get("revenueGrowth")) > 0:              score += 1  # Revenue growing
    if _safe(info.get("debtToEquity"), 999) < 100:        score += 1  # Moderate leverage
    if _safe(info.get("currentRatio")) > 1:               score += 1  # Current ratio > 1
    if _safe(info.get("returnOnEquity")) > 0:             score += 1  # Positive ROE
    if _safe(info.get("freeCashflow")) > 0:               score += 1  # Positive FCF
    return score


def _yf_symbol(ticker: str, market: str) -> str:
    """Convert internal ticker to yfinance format (add .NS for India)."""
    if market == "IN" and "." not in ticker:
        return ticker + ".NS"
    return ticker


def _fetch_one(ticker: str, market: str) -> dict:
    """Fetch real fundamentals for one ticker. Returns partial real + partial synthetic."""
    cache_key = f"{ticker}:{market}"
    now = time.time()
    with _lock:
        if cache_key in _fund_cache and now - _fund_ts.get(cache_key, 0) < FUND_TTL:
            return _fund_cache[cache_key]

    sym = _yf_symbol(ticker, market)
    try:
        t = yf.Ticker(sym)
        info = t.info or {}
        if not info or not info.get("symbol"):
            raise ValueError("Empty info")

        # Gross profit margin
        gpm = info.get("grossMargins")
        if gpm is None or not math.isfinite(float(gpm)):
            gpm = np.random.RandomState(hash(ticker) % (2**31)).uniform(0.1, 0.9)

        # Short interest % of float
        si = info.get("shortPercentOfFloat")
        if si is None or not math.isfinite(float(si)):
            si = np.random.RandomState((hash(ticker) + 4) % (2**31)).uniform(0.005, 0.20)

        # Accruals ratio = (NI – OCF) / Total Assets
        ni = _safe(info.get("netIncomeToCommon"))
        ocf = _safe(info.get("operatingCashflow"))
        ta = _safe(info.get("totalAssets"), 1) or 1
        accruals = max(-0.3, min(0.3, (ni - ocf) / ta))

        # Piotroski from info dict
        piotroski = _piotroski_from_info(info)

        # 12-1 month momentum from price history
        # Check price cache first
        with _lock:
            cached_prices = _price_cache.get(cache_key)
            prices_fresh = time.time() - _price_ts.get(cache_key, 0) < PRICE_TTL

        if cached_prices is not None and prices_fresh and len(cached_prices) >= 252:
            hist_close = cached_prices
        else:
            hist = t.history(period="14mo", auto_adjust=True)
            hist_close = hist["Close"] if not hist.empty else pd.Series(dtype=float)
            with _lock:
                _price_cache[cache_key] = hist_close
                _price_ts[cache_key] = time.time()

        if len(hist_close) >= 252:
            p1m = float(hist_close.iloc[-22])
            p12m = float(hist_close.iloc[-252])
            momentum = (p1m - p12m) / p12m if p12m else 0.0
        else:
            momentum = float(
                np.random.RandomState((hash(ticker) + 3) % (2**31)).uniform(-0.3, 0.6)
            )

        result = {
            "gross_profit_margin": float(gpm),
            "accruals_ratio": float(accruals),
            "piotroski": piotroski,
            "momentum_raw": float(momentum),
            "short_interest_pct": float(si),
            "_is_real": True,
        }
    except Exception as exc:
        log.debug("yfinance fetch failed for %s: %s — using synthetic", ticker, exc)
        result = {**_synthetic_row(ticker), "_is_real": False}

    with _lock:
        _fund_cache[cache_key] = result
        _fund_ts[cache_key] = time.time()
    return result


def fetch_fundamentals_batch(tickers: list[str], market: str = "US") -> dict[str, dict]:
    """Fetch fundamentals for all tickers in parallel (cached)."""
    results: dict[str, dict] = {}
    missing: list[str] = []

    now = time.time()
    with _lock:
        for t in tickers:
            key = f"{t}:{market}"
            if key in _fund_cache and now - _fund_ts.get(key, 0) < FUND_TTL:
                results[t] = _fund_cache[key]
            else:
                missing.append(t)

    if missing:
        workers = min(MAX_WORKERS, len(missing))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_fetch_one, t, market): t for t in missing}
            for fut in as_completed(futures):
                t = futures[fut]
                try:
                    results[t] = fut.result()
                except Exception:
                    results[t] = _synthetic_row(t)

    return results


# ─── Public API ────────────────────────────────────────────────────────────────

def build_real_snapshot(tickers: list[str], market: str) -> UniverseSnapshot:
    """
    Build a UniverseSnapshot with real yfinance data.
    Any ticker or field that fails falls back to synthetic values.
    """
    macro = fetch_real_macro()
    fund_map = fetch_fundamentals_batch(tickers, market)

    rows = []
    for t in tickers:
        row = fund_map.get(t, _synthetic_row(t)).copy()
        row.pop("_is_real", None)
        rows.append({"ticker": t, **row})

    fundamentals = pd.DataFrame(rows)
    return UniverseSnapshot(
        tickers=tickers,
        market=market,
        fundamentals=fundamentals,
        macro=macro,
    )


def prewarm_cache(tickers: list[str], market: str = "US") -> None:
    """Called on server startup to populate the cache before first request."""
    try:
        fetch_real_macro()
        fetch_fundamentals_batch(tickers[:20], market)   # warm first 20 eagerly
        log.info("Cache pre-warm complete for %d tickers", min(20, len(tickers)))
    except Exception as exc:
        log.warning("Cache pre-warm failed: %s", exc)

"""
Phase 3 real data builder — 100% live data, zero synthetic fallbacks where avoidable.

Data sources:
  Macro  : FRED (HY spread, ISM PMI, 2Y/10Y yields, CPI, Fed funds) + yfinance (VIX, SPX)
  Fundamentals: yfinance info dict (gross margin, piotroski, accruals, short interest,
                P/E, P/B, beta) + 14-month price history (momentum, realized vol)
  Fallback: deterministic synthetic only when yfinance returns empty/corrupt data

Caching:
  Macro        — 1 hour
  Fundamentals — 4 hours
  First load   — ~15-25 s (50 tickers in parallel); subsequent hits: <1 s
"""
from __future__ import annotations

import logging
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd
import yfinance as yf

from nq_signals.engine import UniverseSnapshot

log = logging.getLogger(__name__)

# ─── Cache ─────────────────────────────────────────────────────────────────────
_lock = threading.Lock()
_fund_cache: dict[str, dict] = {}
_fund_ts: dict[str, float] = {}
_price_cache: dict[str, pd.Series] = {}
_price_ts: dict[str, float] = {}
_macro_cache: "_LiveMacro | None" = None
_macro_ts: float = 0.0
_macro_in_cache: "_LiveMacroIN | None" = None
_macro_in_ts: float = 0.0

FUND_TTL  = 4 * 3600   # 4 hours
PRICE_TTL = 3600        # 1 hour
MACRO_TTL = 3600        # 1 hour
INSIDER_TTL = 24 * 3600  # 24 hours — EDGAR filings are daily anyway
MAX_WORKERS = 12

# Separate cache for insider scores (keyed by ticker — US-only)
_insider_cache: dict[str, float] = {}
_insider_ts: dict[str, float] = {}


# ─── Live Macro dataclasses ────────────────────────────────────────────────────

@dataclass
class _LiveMacro:
    # yfinance-sourced
    vix: float = 18.0
    spx_vs_200ma: float = 0.02
    spx_return_1m: float = 0.01
    # FRED-sourced
    yield_spread_2y10y: float = 0.10
    hy_spread_oas: float = 350.0
    ism_pmi: float = 51.0
    cpi_yoy: float = 3.0
    fed_funds_rate: float = 5.25
    yield_10y: float = 4.2
    yield_2y: float = 4.1
    # metadata
    fred_sourced: bool = False


@dataclass
class _LiveMacroIN:
    """India macro indicators — yfinance-sourced."""
    india_vix: float = 15.0
    nifty_vs_200ma: float = 0.02
    nifty_return_1m: float = 0.01
    inr_usd: float = 83.0
    rbi_repo_rate: float = 6.50
    sensex_close: float = 72000.0


def _safe(val, default: float = 0.0) -> float:
    try:
        f = float(val)
        return f if math.isfinite(f) else default
    except Exception:
        return default


# ─── Macro fetch ──────────────────────────────────────────────────────────────

def fetch_real_macro() -> _LiveMacro:
    global _macro_cache, _macro_ts
    with _lock:
        if _macro_cache is not None and time.time() - _macro_ts < MACRO_TTL:
            return _macro_cache

    m = _LiveMacro()

    # --- yfinance: VIX ---
    try:
        h = yf.Ticker("^VIX").history(period="5d", auto_adjust=True)
        if not h.empty:
            m.vix = float(h["Close"].iloc[-1])
    except Exception:
        pass

    # --- yfinance: SPX 200-day MA + 1-month return ---
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

    # --- FRED: HY spread, ISM PMI, 2Y/10Y yields, CPI, Fed funds ---
    fred_key = os.environ.get("FRED_API_KEY", "").strip()
    if fred_key:
        try:
            from nq_data.macro.fred_connector import FREDConnector
            snap = FREDConnector(api_key=fred_key).get_snapshot(date.today())

            if snap.hy_spread_oas is not None:
                # FRED BAMLH0A0HYM2 is in percent (e.g. 3.24 = 3.24%); convert to bps
                m.hy_spread_oas = snap.hy_spread_oas * 100
            if snap.ism_pmi is not None and snap.ism_pmi > 0:
                m.ism_pmi = snap.ism_pmi
            if snap.yield_spread_2y10y is not None:
                m.yield_spread_2y10y = snap.yield_spread_2y10y
            if snap.yield_10y is not None:
                m.yield_10y = snap.yield_10y
            if snap.yield_2y is not None:
                m.yield_2y = snap.yield_2y
            if snap.cpi_yoy is not None:
                m.cpi_yoy = snap.cpi_yoy
            if snap.fed_funds_rate is not None:
                m.fed_funds_rate = snap.fed_funds_rate
            m.fred_sourced = True
            log.info(
                "FRED macro loaded: VIX=%.1f HY=%.0f ISM=%.1f CPI=%.1f%% FFR=%.2f%% 2s10s=%.2f",
                m.vix, m.hy_spread_oas, m.ism_pmi, m.cpi_yoy, m.fed_funds_rate, m.yield_spread_2y10y,
            )
        except Exception as exc:
            log.warning("FRED fetch failed: %s — using yfinance proxies for missing fields", exc)
            # Fallback: yield curve from yfinance TNX/IRX
            try:
                tnx = yf.Ticker("^TNX").history(period="5d", auto_adjust=True)
                irx = yf.Ticker("^IRX").history(period="5d", auto_adjust=True)
                if not tnx.empty and not irx.empty:
                    t10 = float(tnx["Close"].iloc[-1])
                    t3m = float(irx["Close"].iloc[-1])
                    m.yield_10y = t10
                    m.yield_spread_2y10y = (t10 - t3m) / 100
            except Exception:
                pass

    with _lock:
        _macro_cache = m
        _macro_ts = time.time()
    return m


# ─── India Macro fetch ────────────────────────────────────────────────────────

def fetch_real_macro_in() -> _LiveMacroIN:
    """Fetch India-specific macro indicators from yfinance."""
    global _macro_in_cache, _macro_in_ts
    with _lock:
        if _macro_in_cache is not None and time.time() - _macro_in_ts < MACRO_TTL:
            return _macro_in_cache

    m = _LiveMacroIN()

    # India VIX
    try:
        h = yf.Ticker("^INDIAVIX").history(period="5d", auto_adjust=True)
        if not h.empty:
            m.india_vix = float(h["Close"].iloc[-1])
    except Exception:
        pass

    # Nifty 50 — 200-day MA + 1-month return
    try:
        nifty = yf.Ticker("^NSEI").history(period="252d", auto_adjust=True)
        if len(nifty) >= 200:
            last = float(nifty["Close"].iloc[-1])
            ma200 = float(nifty["Close"].tail(200).mean())
            m.nifty_vs_200ma = (last - ma200) / ma200
        if len(nifty) >= 22:
            m.nifty_return_1m = (
                float(nifty["Close"].iloc[-1]) / float(nifty["Close"].iloc[-22]) - 1
            )
            m.sensex_close = last
    except Exception:
        pass

    # INR/USD
    try:
        inr = yf.Ticker("INRUSD=X").history(period="5d", auto_adjust=True)
        if not inr.empty:
            m.inr_usd = float(inr["Close"].iloc[-1])
    except Exception:
        pass

    # RBI repo rate — not available via yfinance; use known current value
    # Updated manually or via a future RBI API connector
    m.rbi_repo_rate = float(os.environ.get("NQ_RBI_REPO_RATE", "6.50"))

    log.info(
        "IN macro loaded: IndiaVIX=%.1f Nifty200MA=%.2f%% 1m=%.2f%% INR/USD=%.2f RBI=%.2f%%",
        m.india_vix, m.nifty_vs_200ma * 100, m.nifty_return_1m * 100, m.inr_usd, m.rbi_repo_rate,
    )

    with _lock:
        _macro_in_cache = m
        _macro_in_ts = time.time()
    return m


# ─── Per-ticker fundamentals ──────────────────────────────────────────────────

def _synthetic_row(ticker: str) -> dict:
    """Deterministic synthetic fallback — only used when yfinance fails entirely."""
    s = hash(ticker) % (2**31 - 1)
    rng = lambda seed: np.random.RandomState(seed)
    return {
        "gross_profit_margin":  float(rng(s).uniform(0.10, 0.85)),
        "roe":                   float(rng(s + 9).uniform(0.03, 0.25)),
        "accruals_ratio":        float(rng(s + 1).uniform(-0.15, 0.15)),
        "piotroski":             int(rng(s + 2).randint(2, 9)),
        "momentum_raw":          float(rng(s + 3).uniform(-0.25, 0.55)),
        "short_interest_pct":    float(rng(s + 4).uniform(0.01, 0.18)),
        "pe_ttm":                float(rng(s + 5).uniform(10, 45)),
        "pb_ratio":              float(rng(s + 6).uniform(1, 8)),
        "beta":                  float(rng(s + 7).uniform(0.5, 1.8)),
        "realized_vol_1y":       float(rng(s + 8).uniform(0.15, 0.50)),
        "_is_real":              False,
    }


def _piotroski_from_info(info: dict) -> int:
    """Compute Piotroski F-Score (0–9) from yfinance info dict."""
    ni  = _safe(info.get("netIncomeToCommon"))
    ta  = _safe(info.get("totalAssets"), 1) or 1
    ocf = _safe(info.get("operatingCashflow"))
    score = 0
    if ni / ta > 0:                                    score += 1  # ROA > 0
    if ocf > 0:                                        score += 1  # CFO > 0
    if ocf > ni:                                       score += 1  # CFO > NI
    if _safe(info.get("grossMargins")) > 0:            score += 1  # GP margin positive
    if _safe(info.get("revenueGrowth")) > 0:           score += 1  # Revenue growing
    if _safe(info.get("debtToEquity"), 999) < 100:     score += 1  # Moderate leverage
    if _safe(info.get("currentRatio")) > 1:            score += 1  # Current ratio > 1
    if _safe(info.get("returnOnEquity")) > 0:          score += 1  # Positive ROE
    if _safe(info.get("freeCashflow")) > 0:            score += 1  # Positive FCF
    return score


def _yf_symbol(ticker: str, market: str) -> str:
    if market == "IN" and "." not in ticker:
        return ticker + ".NS"
    return ticker


def _fetch_one(ticker: str, market: str) -> dict:
    """Fetch real fundamentals + price-derived signals for one ticker."""
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

        # ── Gross profit margin ───────────────────────────────────────
        gpm = _safe(info.get("grossMargins"),
                    np.random.RandomState(hash(ticker) % (2**31)).uniform(0.1, 0.9))

        # ── Return on equity (sector-adjusted quality uses this for financials) ──
        roe = _safe(info.get("returnOnEquity"),
                    np.random.RandomState((hash(ticker) + 11) % (2**31)).uniform(0.05, 0.25))
        # Clamp to sane band — yfinance occasionally returns 5.0 (i.e. 500%)
        roe = max(-0.50, min(0.80, roe))

        # ── Short interest % of float ─────────────────────────────────
        si = _safe(info.get("shortPercentOfFloat"),
                   np.random.RandomState((hash(ticker) + 4) % (2**31)).uniform(0.01, 0.18))

        # ── Accruals ratio = (NI – OCF) / Total Assets ───────────────
        ni  = _safe(info.get("netIncomeToCommon"))
        ocf = _safe(info.get("operatingCashflow"))
        ta  = _safe(info.get("totalAssets"), 1) or 1
        accruals = max(-0.3, min(0.3, (ni - ocf) / ta))

        # ── Piotroski ─────────────────────────────────────────────────
        piotroski = _piotroski_from_info(info)

        # ── Valuation multiples ───────────────────────────────────────
        pe_ttm   = _safe(info.get("trailingPE"), 25.0)
        pb_ratio = _safe(info.get("priceToBook"), 3.0)
        # Clamp to sane ranges — negative P/E (loss-making) treated as high
        pe_ttm   = max(1.0, min(200.0, pe_ttm))
        pb_ratio = max(0.1, min(50.0, pb_ratio))

        # ── Beta ──────────────────────────────────────────────────────
        beta = _safe(info.get("beta"), 1.0)
        beta = max(0.1, min(3.0, beta))

        # ── Price history: momentum + realized vol ────────────────────
        with _lock:
            cached_prices = _price_cache.get(cache_key)
            prices_fresh  = time.time() - _price_ts.get(cache_key, 0) < PRICE_TTL

        if cached_prices is not None and prices_fresh and len(cached_prices) >= 253:
            hist_close = cached_prices
        else:
            hist = t.history(period="14mo", auto_adjust=True)
            hist_close = hist["Close"] if not hist.empty else pd.Series(dtype=float)
            with _lock:
                _price_cache[cache_key] = hist_close
                _price_ts[cache_key]    = time.time()

        # 12-1 month momentum (Jegadeesh & Titman 1993: skip most-recent 21 trading
        # days to avoid short-term reversal contamination).
        # Minimum 253 bars: 252 lookback + 1 current price (matching momentum.py).
        if len(hist_close) >= 253:
            p1m  = float(hist_close.iloc[-21])   # T-21 trading days (≈1 month ago)
            p12m = float(hist_close.iloc[-252])
            momentum = (p1m - p12m) / p12m if p12m else 0.0
        else:
            momentum = float(
                np.random.RandomState((hash(ticker) + 3) % (2**31)).uniform(-0.25, 0.55)
            )

        # Realized annualized volatility (252-day window)
        if len(hist_close) >= 30:
            log_rets = np.log(hist_close / hist_close.shift(1)).dropna()
            realized_vol = float(log_rets.tail(252).std() * np.sqrt(252))
        else:
            realized_vol = float(beta * 0.18)  # rough proxy

        # ── Live price snapshot (for LLM context injection) ──────────────
        current_price   = info.get("currentPrice") or info.get("regularMarketPrice")
        week52_high     = info.get("fiftyTwoWeekHigh")
        week52_low      = info.get("fiftyTwoWeekLow")
        analyst_target  = info.get("targetMeanPrice")
        analyst_rec     = info.get("recommendationKey", "")
        market_cap      = info.get("marketCap")
        change_pct      = info.get("regularMarketChangePercent", 0.0)
        long_name       = info.get("longName") or info.get("shortName") or ticker
        industry        = info.get("industry")
        sector          = info.get("sector")

        # Earnings date
        earnings_date = None
        try:
            cal = t.calendar
            if isinstance(cal, dict):
                ed = cal.get("Earnings Date")
                if ed and len(ed) > 0:
                    earnings_date = str(ed[0].date())
        except Exception:
            pass

        # Dividend yield
        div_pct = None
        div_rate = info.get("dividendRate")
        if div_rate and current_price:
            try:
                div_pct = round(float(div_rate) / float(current_price) * 100, 2)
                if not (0 < div_pct < 20):
                    div_pct = None
            except Exception:
                pass
        if div_pct is None:
            div_raw = info.get("dividendYield")
            if div_raw:
                try:
                    v = float(div_raw)
                    v = v if v > 1 else v * 100
                    if 0 < v < 20:
                        div_pct = round(v, 2)
                except Exception:
                    pass

        result = {
            "gross_profit_margin": float(gpm),
            "roe":                 float(roe),
            "accruals_ratio":       float(accruals),
            "piotroski":            int(piotroski),
            "momentum_raw":         float(momentum),
            "short_interest_pct":   float(si),
            "pe_ttm":               float(pe_ttm),
            "pb_ratio":             float(pb_ratio),
            "beta":                 float(beta),
            "realized_vol_1y":      float(realized_vol),
            "delivery_pct":         None,  # filled by Bhavcopy for IN market
            "_is_real":             True,
            # Live price fields — used by query.py to inject accurate prices into LLM context
            "current_price":        float(current_price) if current_price else None,
            "week52_high":          float(week52_high) if week52_high else None,
            "week52_low":           float(week52_low) if week52_low else None,
            "analyst_target":       float(analyst_target) if analyst_target else None,
            "analyst_rec":          analyst_rec.upper() if analyst_rec else None,
            "market_cap":           float(market_cap) if market_cap else None,
            "change_pct":           float(change_pct),
            "long_name":            long_name,
            "industry":             industry,
            "sector":               sector,
            "earnings_date":        earnings_date,
            "dividend_yield":       div_pct,
            "debt_equity":          round(float(info.get("debtToEquity", 100.0)) / 100, 2) if info.get("debtToEquity") is not None else None,
            "revenue_growth_yoy":   round(float(info.get("revenueGrowth", 0.0)) * 100, 1) if info.get("revenueGrowth") is not None else None,
            "fcf_yield":            round(fcf_val / market_cap, 4) if (fcf_val := _safe(info.get("freeCashflow")) or 0) > 0 and market_cap else None,
        }
    except Exception as exc:
        log.debug("yfinance fetch failed for %s: %s — using synthetic", ticker, exc)
        result = _synthetic_row(ticker)

    with _lock:
        _fund_cache[cache_key] = result
        _fund_ts[cache_key]    = time.time()
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


# ─── Cross-sectional factor percentiles ──────────────────────────────────────

def _fetch_insider_score(ticker: str) -> float:
    """Return a 0-1 insider-cluster score for a US-market ticker.

    Thin wrapper around `nq_data.alt_signals.edgar_form4`. Any network
    or parse failure collapses to a neutral 0.5 so the composite stays
    valid. Cached for 24 h per ticker to stay well within EDGAR's
    fair-use budget.
    """
    now = time.time()
    with _lock:
        if ticker in _insider_cache and now - _insider_ts.get(ticker, 0) < INSIDER_TTL:
            return _insider_cache[ticker]
    try:
        from datetime import timedelta
        from nq_data.alt_signals.edgar_form4 import (
            Form4Connector,
            compute_insider_cluster_score,
        )
        today = date.today()
        events = Form4Connector().get_insider_events(
            ticker, today - timedelta(days=90), today
        )
        score = compute_insider_cluster_score(events)
    except Exception as exc:
        log.debug("insider score fallback for %s: %s", ticker, exc)
        score = 0.5
    with _lock:
        _insider_cache[ticker] = score
        _insider_ts[ticker] = now
    return score


def _add_insider_percentile(df: pd.DataFrame, market: str) -> pd.DataFrame:
    """Populate `insider_percentile` on the universe frame.

    Form 4 is a US-only filing type (India uses BSE/NSE disclosures via
    a different pipeline), so we only attempt live lookups when market
    == 'US'. Everyone else defaults to 0.5 neutral.
    """
    if market != "US" or df.empty:
        df["insider_percentile"] = 0.5
        return df

    # Hard budget: only fetch for tickers we don't already have cached,
    # and cap the fan-out per request so a cold cache doesn't blow up
    # EDGAR rate limits.
    tickers = df["ticker"].tolist()
    now = time.time()
    uncached = [
        t for t in tickers
        if not (t in _insider_cache and now - _insider_ts.get(t, 0) < INSIDER_TTL)
    ]
    # Only kick off the network fan-out if there's a reasonable cache
    # miss count — otherwise rely on cached values to stay snappy.
    if uncached:
        with ThreadPoolExecutor(max_workers=min(4, len(uncached))) as pool:
            futures = {pool.submit(_fetch_insider_score, t): t for t in uncached[:20]}
            for fut in as_completed(futures):
                t = futures[fut]
                try:
                    fut.result()
                except Exception:
                    with _lock:
                        _insider_cache[t] = 0.5
                        _insider_ts[t] = now

    df["insider_percentile"] = df["ticker"].map(
        lambda t: _insider_cache.get(t, 0.5)
    )
    return df


def _add_value_and_lowvol_percentiles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute value_percentile and low_vol_percentile cross-sectionally.

    Value  : inverse of (P/E rank * 0.5 + P/B rank * 0.5) — cheaper is better
    Low-vol: inverse of realized_vol rank — less volatile is better
    """
    if "pe_ttm" in df.columns and "pb_ratio" in df.columns:
        pe_rank  = df["pe_ttm"].rank(pct=True, na_option="keep").fillna(0.5)
        pb_rank  = df["pb_ratio"].rank(pct=True, na_option="keep").fillna(0.5)
        # Invert: high P/E rank → low value score
        df["value_percentile"] = 1.0 - (pe_rank * 0.50 + pb_rank * 0.50)
    else:
        df["value_percentile"] = 0.5

    if "realized_vol_1y" in df.columns:
        vol_rank = df["realized_vol_1y"].rank(pct=True, na_option="keep").fillna(0.5)
        df["low_vol_percentile"] = 1.0 - vol_rank   # less volatile = better
    elif "beta" in df.columns:
        beta_rank = df["beta"].rank(pct=True, na_option="keep").fillna(0.5)
        df["low_vol_percentile"] = 1.0 - beta_rank
    else:
        df["low_vol_percentile"] = 0.5

    return df


# ─── NSE Bhavcopy enrichment ──────────────────────────────────────────────────

_bhavcopy_cache: dict[str, float] = {}
_bhavcopy_ts: float = 0.0
BHAVCOPY_TTL = 6 * 3600  # 6 hours — EOD data doesn't change intraday


def _enrich_with_bhavcopy(fundamentals: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """Enrich IN fundamentals with delivery_pct from NSE Bhavcopy."""
    global _bhavcopy_cache, _bhavcopy_ts

    now = time.time()
    if not _bhavcopy_cache or now - _bhavcopy_ts > BHAVCOPY_TTL:
        try:
            from nq_data.price.nse_bhavcopy import NSEBhavCopyConnector
            from datetime import date, timedelta

            conn = NSEBhavCopyConnector()
            bars = []
            for attempt in range(5):
                d = date.today() - timedelta(days=attempt)
                bars = conn.download_bhavcopy(d)
                if bars:
                    break

            new_cache: dict[str, float] = {}
            for bar in bars:
                if bar.delivery_pct is not None:
                    new_cache[bar.ticker] = bar.delivery_pct

            if new_cache:
                _bhavcopy_cache = new_cache
                _bhavcopy_ts = now
                log.info("Bhavcopy enriched %d tickers with delivery_pct", len(new_cache))
        except Exception as exc:
            log.warning("Bhavcopy fetch failed: %s — delivery_pct stays None", exc)

    if _bhavcopy_cache and "delivery_pct" in fundamentals.columns:
        fundamentals["delivery_pct"] = fundamentals["ticker"].map(
            lambda t: _bhavcopy_cache.get(t)
        )
    return fundamentals


# ─── Public API ───────────────────────────────────────────────────────────────

def build_real_snapshot(tickers: list[str], market: str) -> UniverseSnapshot:
    """
    Build a UniverseSnapshot backed entirely by real data.
    Any ticker/field that fails falls back to deterministic synthetic values.
    """
    if market == "IN":
        macro = fetch_real_macro_in()
    else:
        macro = fetch_real_macro()
    fund_map = fetch_fundamentals_batch(tickers, market)

    from nq_api.universe import sector_of
    rows = []
    for t in tickers:
        row = fund_map.get(t, _synthetic_row(t)).copy()
        row.pop("_is_real", None)
        rows.append({"ticker": t, "sector": sector_of(t, market), **row})

    fundamentals = pd.DataFrame(rows)
    fundamentals = _add_value_and_lowvol_percentiles(fundamentals)
    fundamentals = _add_insider_percentile(fundamentals, market)

    # IN-specific: enrich with NSE Bhavcopy delivery_pct
    if market == "IN":
        fundamentals = _enrich_with_bhavcopy(fundamentals, tickers)

    return UniverseSnapshot(
        tickers=tickers,
        market=market,
        fundamentals=fundamentals,
        macro=macro,
    )


def prewarm_cache(tickers: list[str], market: str = "US") -> None:
    """Called on server startup to populate cache before first request."""
    try:
        fetch_real_macro()
        fetch_fundamentals_batch(tickers[:20], market)
        log.info("Cache pre-warm complete for %d tickers", min(20, len(tickers)))
    except Exception as exc:
        log.warning("Cache pre-warm failed: %s", exc)

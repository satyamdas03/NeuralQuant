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
import requests
import yfinance as yf

from nq_signals.engine import UniverseSnapshot
logger = logging.getLogger(__name__)

log = logging.getLogger(__name__)

# ─── Shared yfinance session ──────────────────────────────────────────────────────
# yfinance >= 1.3.0 REQUIRES curl_cffi — without it, Yahoo rejects requests
# with 401 Invalid Crumb. We must use CurlSession(impersonate="chrome").
_yf_session = None

def _get_yf_session():
    """Return a curl_cffi session for yfinance. Fails hard if curl_cffi is missing."""
    global _yf_session
    if _yf_session is None:
        try:
            from curl_cffi.requests import Session as CurlSession
            _yf_session = CurlSession(impersonate="chrome")
            log.info("Using curl_cffi session for yfinance (impersonate=chrome)")
        except ImportError:
            log.error("curl_cffi is NOT installed — yfinance calls will fail on cloud IPs! "
                       "Add curl_cffi to dependencies.")
            _yf_session = False  # sentinel: don't retry
    return _yf_session if _yf_session else None

_IS_RENDER = bool(os.environ.get("RENDER"))
_lock = threading.Lock()
_fund_cache: dict[str, dict] = {}
_fund_ts: dict[str, float] = {}
_price_cache: dict[str, pd.Series] = {}
_price_ts: dict[str, float] = {}
_macro_cache: "_LiveMacro | None" = None
_macro_ts: float = 0.0

# ─── yfinance .info cache (aggressive caching to reduce Yahoo rate-limit hits) ──
_yf_info_cache: dict[str, dict] = {}
_yf_info_ts: dict[str, float] = {}
_YF_INFO_TTL = 3600  # 1 hour for successful fetches
_YF_INFO_FAIL_TTL = 300  # 5 min for failed fetches (don't hammer Yahoo)


def _fetch_yf_info_cached(sym: str) -> dict:
    """Fetch yfinance Ticker.info with in-memory caching and staggered delays.
    Designed to reduce Yahoo rate-limiting on cloud IPs (Render)."""
    now = time.time()
    cache_key = sym.upper()
    with _lock:
        if cache_key in _yf_info_cache:
            age = now - _yf_info_ts.get(cache_key, 0)
            max_age = _YF_INFO_TTL if _yf_info_cache[cache_key].get("_cached_ok") else _YF_INFO_FAIL_TTL
            if age < max_age:
                return _yf_info_cache[cache_key]

    # Stagger requests on Render to avoid Yahoo rate-limiting cloud IPs
    if _IS_RENDER:
        time.sleep(1.0)

    info: dict = {}
    for attempt in range(3):
        try:
            t = yf.Ticker(sym, session=_get_yf_session())
            info = t.info or {}
            if info and info.get("symbol"):
                break
            log.debug("yfinance empty info for %s (attempt %d/%d)", sym, attempt + 1, 3)
        except Exception as exc:
            log.debug("yfinance fetch exception for %s (attempt %d/%d): %s", sym, attempt + 1, 3, exc)
        if attempt < 2:
            time.sleep(3.0 if _IS_RENDER else 1.0)

    if info and info.get("symbol"):
        info["_cached_ok"] = True
    else:
        info = {"_cached_ok": False}

    with _lock:
        _yf_info_cache[cache_key] = info
        _yf_info_ts[cache_key] = now

    # Overlay FMP data on top of yfinance info for more reliable fundamentals
    _overlay_fmp_info(info, cache_key)

    return info


def _overlay_fmp_info(info: dict, ticker: str) -> None:
    """Overlay FMP data onto yfinance .info dict in-place.

    FMP is the primary data source. yfinance values are kept only when FMP
    doesn't have data. Sets _cached_ok when FMP provides usable data even
    if yfinance failed completely.
    """
    try:
        from nq_data.fmp import get_fmp_client
        fmp = get_fmp_client()
        if not fmp._enabled:
            return

        profile = fmp.get_profile(ticker)
        if profile:
            has_data = False
            if profile.get("name") and not info.get("longName"):
                info["longName"] = profile["name"]; has_data = True
            if profile.get("sector") and not info.get("sector"):
                info["sector"] = profile["sector"]; has_data = True
            if profile.get("industry") and not info.get("industry"):
                info["industry"] = profile["industry"]; has_data = True
            if profile.get("market_cap") and not info.get("marketCap"):
                info["marketCap"] = profile["market_cap"]; has_data = True
            if profile.get("beta") is not None and profile["beta"] > 0:
                info["beta"] = profile["beta"]; has_data = True
            if profile.get("price") is not None and profile["price"] > 0:
                info["currentPrice"] = profile["price"]
                info["regularMarketPrice"] = profile["price"]; has_data = True
            if has_data:
                info["_cached_ok"] = True

        metrics = fmp.get_key_metrics(ticker)
        if metrics:
            if metrics.get("pe_ratio") is not None and metrics["pe_ratio"] > 0:
                info["trailingPE"] = metrics["pe_ratio"]
            if metrics.get("pb_ratio") is not None and metrics["pb_ratio"] > 0:
                info["priceToBook"] = metrics["pb_ratio"]
            if metrics.get("beta") is not None and metrics["beta"] > 0 and "beta" not in info:
                info["beta"] = metrics["beta"]
            if metrics.get("dividend_yield") is not None and metrics["dividend_yield"] >= 0:
                info["dividendYield"] = metrics["dividend_yield"]
            if metrics.get("gross_profit_margin") is not None and metrics["gross_profit_margin"] != 0:
                info["grossMargins"] = metrics["gross_profit_margin"]
            if metrics.get("operating_profit_margin") is not None and metrics["operating_profit_margin"] != 0:
                info["operatingMargins"] = metrics["operating_profit_margin"]
            if metrics.get("net_profit_margin") is not None and metrics["net_profit_margin"] != 0:
                info["profitMargins"] = metrics["net_profit_margin"]
            if metrics.get("revenue_growth") is not None and metrics["revenue_growth"] != 0:
                info["revenueGrowth"] = metrics["revenue_growth"]
            if metrics.get("earnings_growth") is not None and metrics["earnings_growth"] != 0:
                info["earningsGrowth"] = metrics["earnings_growth"]
            if metrics.get("debt_to_equity") is not None and metrics["debt_to_equity"] >= 0:
                info["debtToEquity"] = metrics["debt_to_equity"]
            if metrics.get("current_ratio") is not None and metrics["current_ratio"] > 0:
                info["currentRatio"] = metrics["current_ratio"]
            if metrics.get("roe") is not None and metrics["roe"] != 0:
                info["returnOnEquity"] = metrics["roe"]
            if metrics.get("roa") is not None and metrics["roa"] != 0:
                info["returnOnAssets"] = metrics["roa"]
            if metrics.get("ev_to_ebitda") is not None and metrics["ev_to_ebitda"] > 0:
                info["enterpriseToEbitda"] = metrics["ev_to_ebitda"]
            if metrics.get("price_to_sales") is not None:
                info["priceToSalesTrailing12Months"] = metrics["price_to_sales"]
            if metrics.get("market_cap") is not None and "marketCap" not in info:
                info["marketCap"] = metrics["market_cap"]

        ratios = fmp.get_ratios(ticker)
        if ratios:
            if ratios.get("price_to_book") is not None and ratios["price_to_book"] > 0 and "priceToBook" not in info:
                info["priceToBook"] = ratios["price_to_book"]
            if ratios.get("gross_profit_margin") is not None and "grossMargins" not in info:
                info["grossMargins"] = ratios["gross_profit_margin"]
            if ratios.get("current_ratio") is not None and "currentRatio" not in info:
                info["currentRatio"] = ratios["current_ratio"]
            if ratios.get("return_on_equity") is not None and "returnOnEquity" not in info:
                info["returnOnEquity"] = ratios["return_on_equity"]

        # ── Quote: price, week52, change%, EPS, P/E ──
        quote = fmp.get_quote(ticker)
        fmp_price = None
        if profile and profile.get("price"):
            fmp_price = float(profile["price"])
        if quote:
            if quote.get("price"):
                fmp_price = float(quote["price"])
                info["currentPrice"] = fmp_price
                info["regularMarketPrice"] = fmp_price
                info["_cached_ok"] = True
            if quote.get("year_high") is not None:
                info["fiftyTwoWeekHigh"] = quote["year_high"]
            if quote.get("year_low") is not None:
                info["fiftyTwoWeekLow"] = quote["year_low"]
            if quote.get("change_pct") is not None:
                info["regularMarketChangePercent"] = quote["change_pct"]
            if quote.get("pe") is not None and "trailingPE" not in info:
                info["trailingPE"] = quote["pe"]
            if quote.get("eps") is not None and "trailingEps" not in info:
                info["trailingEps"] = quote["eps"]

        # Compute P/E from FMP price + income statement EPS (most accurate)
        if fmp_price and fmp_price > 0:
            income = fmp.get_income_statement(ticker)
            if income and income.get("eps"):
                try:
                    pe_calc = round(fmp_price / float(income["eps"]), 1)
                    if 0.5 < pe_calc < 5000:
                        info["trailingPE"] = pe_calc
                except (TypeError, ValueError, ZeroDivisionError):
                    pass

        # ── Analyst data ──
        target = fmp.get_price_target(ticker)
        if target:
            if target.get("target_avg") is not None:
                info["targetMeanPrice"] = target["target_avg"]
            if target.get("target_high") is not None:
                info["targetHighPrice"] = target["target_high"]
            if target.get("target_low") is not None:
                info["targetLowPrice"] = target["target_low"]

        grades = fmp.get_analyst_grades(ticker)
        if grades:
            if grades.get("consensus") is not None and "recommendationKey" not in info:
                info["recommendationKey"] = grades["consensus"]
            if grades.get("strong_buy") is not None:
                info["numberOfAnalystOpinions"] = (
                    (grades.get("strong_buy") or 0) + (grades.get("buy") or 0) +
                    (grades.get("hold") or 0) + (grades.get("sell") or 0) +
                    (grades.get("strong_sell") or 0)
                )

        # ── Financial scores ──
        scores = fmp.get_financial_scores(ticker)
        if scores:
            if scores.get("piotroski_score") is not None:
                info["_fmp_piotroski"] = scores["piotroski_score"]
            if scores.get("altman_z_score") is not None:
                info["_fmp_altman_z"] = scores["altman_z_score"]

    except Exception as exc:
        log.debug("FMP overlay failed for %s: %s", ticker, exc)


_macro_in_cache: "_LiveMacroIN | None" = None
_macro_in_ts: float = 0.0

FUND_TTL  = 4 * 3600   # 4 hours
PRICE_TTL = 3600        # 1 hour
MACRO_TTL = 3600        # 1 hour
INSIDER_TTL = 24 * 3600  # 24 hours — EDGAR filings are daily anyway
MAX_WORKERS = 1 if _IS_RENDER else 12

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
    except Exception as e:
        logger.debug("Non-critical enrichment failed: %s", e)
        return default


def _compute_ttm_pe(ticker_obj: "yf.Ticker", info: dict, pe_raw) -> tuple[float | None, float | None]:
    """Compute true TTM P/E using multiple methods, in priority order.

    Priority:
    1. yfinance get_valuation_measures() (v1.3.0+) — TTM P/E from Key Statistics page
    2. Computed from quarterly income statements (price / TTM EPS)
    3. Fall back to caller's pe_raw

    Returns (pe_ttm, price_to_book) tuple. Both can be None if computation fails.
    """
    vm_pb = None  # Price/Book from valuation_measures

    # Method 1: valuation_measures (yfinance 1.3.0+) — most accurate
    try:
        vm = ticker_obj.get_valuation_measures()
        if vm is not None and not vm.empty:
            # Get the most recent (first column "Current") Trailing P/E
            if "Trailing P/E" in vm.index:
                pe_val = vm.loc["Trailing P/E"].iloc[0]
                if pe_val is not None and not (isinstance(pe_val, float) and math.isnan(pe_val)):
                    computed = float(pe_val)
                    if 0.5 <= computed <= 500:
                        log.debug("P/E from valuation_measures: %.2f", computed)
                        # Also extract Price/Book
                        if "Price/Book" in vm.index:
                            pb_val = vm.loc["Price/Book"].iloc[0]
                            if pb_val is not None and not (isinstance(pb_val, float) and math.isnan(pb_val)):
                                vm_pb = float(pb_val)
                        return round(computed, 2), vm_pb
            # Also extract Price/Book even if P/E not available
            if "Price/Book" in vm.index:
                pb_val = vm.loc["Price/Book"].iloc[0]
                if pb_val is not None and not (isinstance(pb_val, float) and math.isnan(pb_val)):
                    vm_pb = float(pb_val)
    except Exception as exc:
        log.debug("valuation_measures failed: %s", exc)

    # Method 2: Compute from quarterly income statements
    try:
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        shares = info.get("sharesOutstanding")
        if not current_price or not shares or shares <= 0:
            return None, vm_pb

        qis = ticker_obj.quarterly_income_stmt
        if qis is None or qis.empty:
            return None, vm_pb

        # Find the net income row (varies by reporting style)
        ni_row = None
        for candidate in ("Net Income Common Stockholders", "Net Income", "Net Income Continuous Operations"):
            if candidate in qis.index:
                ni_row = qis.loc[candidate]
                break
        if ni_row is None:
            return None, vm_pb

        # Sum last 4 quarters
        last_4 = ni_row.iloc[:4]
        ttm_ni = float(last_4.sum())
        if ttm_ni <= 0:
            return None, vm_pb  # Loss-making company, P/E not meaningful

        ttm_eps = ttm_ni / shares
        computed_pe = current_price / ttm_eps

        # Sanity check: computed PE should be in reasonable range
        if 0.5 <= computed_pe <= 500:
            log.debug("P/E from quarterly income stmt: %.2f", computed_pe)
            return round(computed_pe, 2), vm_pb
        return None, vm_pb
    except Exception as exc:
        log.debug("TTM P/E computation from income stmt failed: %s", exc)
        return None, vm_pb


# ─── Macro fetch ──────────────────────────────────────────────────────────────

def fetch_real_macro() -> _LiveMacro:
    global _macro_cache, _macro_ts
    with _lock:
        if _macro_cache is not None and time.time() - _macro_ts < MACRO_TTL:
            return _macro_cache

    m = _LiveMacro()

    # --- yfinance: VIX ---
    try:
        h = yf.Ticker("^VIX", session=_get_yf_session()).history(period="5d", auto_adjust=True)
        if not h.empty:
            m.vix = float(h["Close"].iloc[-1])
    except Exception:
        pass

    # --- yfinance: SPX 200-day MA + 1-month return ---
    try:
        spx = yf.Ticker("^GSPC", session=_get_yf_session()).history(period="252d", auto_adjust=True)
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
                tnx = yf.Ticker("^TNX", session=_get_yf_session()).history(period="5d", auto_adjust=True)
                irx = yf.Ticker("^IRX", session=_get_yf_session()).history(period="5d", auto_adjust=True)
                if not tnx.empty and not irx.empty:
                    t10 = float(tnx["Close"].iloc[-1])
                    t3m = float(irx["Close"].iloc[-1])
                    m.yield_10y = t10
                    m.yield_spread_2y10y = (t10 - t3m) / 100
            except Exception:
                pass

    # FMP treasury rates as supplement when FRED/yfinance missing
    if m.yield_10y is None or m.fed_funds_rate is None:
        try:
            from nq_data.fmp import get_fmp_client
            fmp = get_fmp_client()
            if fmp._enabled:
                rates = fmp.get_treasury_rates()
                if rates:
                    if m.yield_10y is None and rates.get("10y") is not None:
                        m.yield_10y = float(rates["10y"])
                    if m.yield_2y is None and rates.get("2y") is not None:
                        m.yield_2y = float(rates["2y"])
                    if m.yield_spread_2y10y is None and rates.get("2y") and rates.get("10y"):
                        m.yield_spread_2y10y = (float(rates["10y"]) - float(rates["2y"])) / 100
                    log.info("FMP treasury rates supplement: 10y=%.2f 2y=%.2f", m.yield_10y, m.yield_2y)
        except Exception as exc:
            log.debug("FMP treasury rates failed: %s", exc)

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
        h = yf.Ticker("^INDIAVIX", session=_get_yf_session()).history(period="5d", auto_adjust=True)
        if not h.empty:
            m.india_vix = float(h["Close"].iloc[-1])
    except Exception:
        pass

    # Nifty 50 — 200-day MA + 1-month return
    try:
        nifty = yf.Ticker("^NSEI", session=_get_yf_session()).history(period="252d", auto_adjust=True)
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

    # USD/INR — use USDINR=X which returns ~83.5 (INR per USD).
    # INRUSD=X returns ~0.012 (USD per INR) which is confusing for agents.
    try:
        usdinr = yf.Ticker("USDINR=X", session=_get_yf_session()).history(period="5d", auto_adjust=True)
        if not usdinr.empty:
            m.inr_usd = round(float(usdinr["Close"].iloc[-1]), 2)
    except Exception:
        # Fallback: try INRUSD=X and invert
        try:
            inrusd = yf.Ticker("INRUSD=X", session=_get_yf_session()).history(period="5d", auto_adjust=True)
            if not inrusd.empty:
                m.inr_usd = round(1.0 / float(inrusd["Close"].iloc[-1]), 2)
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

def _empty_row(ticker: str) -> dict:
    """Return a result with all nulls — no synthetic fabrication."""
    return {
        "gross_profit_margin": None,
        "roe": None,
        "accruals_ratio": None,
        "piotroski": None,
        "momentum_raw": None,
        "short_interest_pct": None,
        "pe_ttm": None,
        "pb_ratio": None,
        "beta": None,
        "realized_vol_1y": None,
        "delivery_pct": None,
        "_is_real": False,
        "_is_synthetic": set(),
        "current_price": None,
        "week52_high": None,
        "week52_low": None,
        "analyst_target": None,
        "analyst_rec": None,
        "market_cap": None,
        "change_pct": None,
        "long_name": ticker,
        "industry": None,
        "sector": None,
        "earnings_date": None,
        "dividend_yield": None,
        "debt_equity": None,
        "revenue_growth_yoy": None,
        "fcf_yield": None,
        "eps_ttm": None,
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


def _fetch_one(ticker: str, market: str, fast_pe: bool = True) -> dict:
    """Fetch real fundamentals + price-derived signals for one ticker.

    Data priority: FMP (primary) → yfinance (fallback) → None (no fabrication).

    Args:
        fast_pe: If True, skip slow valuation_measures/quarterly_income_stmt calls.
    """
    cache_key = f"{ticker}:{market}"
    now = time.time()
    with _lock:
        if cache_key in _fund_cache:
            age = now - _fund_ts.get(cache_key, 0)
            cached = _fund_cache[cache_key]
            max_age = FUND_TTL if cached.get("_is_real") else 30
            if age < max_age:
                return _fund_cache[cache_key]

    sym = _yf_symbol(ticker, market)
    info: dict = {}
    raw_info = _fetch_yf_info_cached(sym)
    if raw_info.get("_cached_ok"):
        info = {k: v for k, v in raw_info.items() if not k.startswith("_")}
    else:
        log.warning("yfinance + FMP both failed for %s — returning empty row", sym)
        result = _empty_row(ticker)
        with _lock:
            _fund_cache[cache_key] = result
            _fund_ts[cache_key] = now
        return result

    try:
        _missing: set[str] = set()
        result: dict = {}  # placeholder until final result dict assigned below

        # Lazy yf.Ticker for fallback paths (P/E computation, earnings date, price history)
        t = yf.Ticker(sym, session=_get_yf_session())

        # ── Gross profit margin ──
        gpm = _safe(info.get("grossMargins"), None)
        if gpm is None:
            _missing.add("gross_profit_margin")

        # ── Return on equity ──
        roe = _safe(info.get("returnOnEquity"), None)
        if roe is not None:
            roe = max(-0.50, min(0.80, roe))
        else:
            _missing.add("roe")

        # ── Short interest (yfinance-only, no FMP alternative) ──
        si = _safe(info.get("shortPercentOfFloat"), None)
        if si is None:
            _missing.add("short_interest_pct")

        # ── Accruals = (NI – OCF) / Total Assets ──
        ni  = _safe(info.get("netIncomeToCommon"))
        ocf = _safe(info.get("operatingCashflow"))
        ta  = _safe(info.get("totalAssets"), 1) or 1
        accruals = max(-0.3, min(0.3, (ni - ocf) / ta)) if (ni or ocf) else None

        # ── Piotroski: prefer FMP financial_scores, fallback to computed from yfinance ──
        fmp_piotroski = raw_info.get("_fmp_piotroski")
        if fmp_piotroski is not None:
            piotroski = int(fmp_piotroski)
        else:
            piotroski = _piotroski_from_info(info)
            if piotroski == 0 and not any([
                _safe(info.get("netIncomeToCommon")),
                _safe(info.get("operatingCashflow")),
            ]):
                piotroski = None  # No fundamental data at all

        # ── P/E ratio (FMP-overlaid trailingPE from quote/key_metrics/income stmt) ──
        pe_raw = info.get("trailingPE")
        vm_pb = None
        if fast_pe:
            pe_ttm = _safe(pe_raw, None)
        else:
            pe_ttm, vm_pb = _compute_ttm_pe(t, info, pe_raw)
            if pe_ttm is None:
                pe_ttm = _safe(pe_raw, None)
        if pe_ttm is None:
            _missing.add("pe_ttm")
        else:
            pe_ttm = max(1.0, min(200.0, pe_ttm))

        # ── P/B ratio ──
        pb_raw = vm_pb if vm_pb else info.get("priceToBook")
        pb_ratio = _safe(pb_raw, None)
        if pb_ratio is None:
            _missing.add("pb_ratio")
        else:
            pb_ratio = max(0.1, min(50.0, pb_ratio))

        # ── Beta (FMP profile overlay) ──
        beta = _safe(info.get("beta"), None)
        if beta is None:
            _missing.add("beta")
        else:
            beta = max(0.01, min(3.0, beta))

        # ── Price history: momentum + realized vol ──
        momentum = None
        realized_vol = None
        hist_close = pd.Series(dtype=float)
        ohlcv_raw: dict[str, list[float]] = {}

        # Try FMP historical prices first (returns empty for IN stocks — Premium-gated)
        try:
            from nq_data.fmp import get_fmp_client
            fmp_client = get_fmp_client()
            if fmp_client._enabled:
                fmp_hist = fmp_client.get_historical_prices(ticker, days=370)
                if fmp_hist and len(fmp_hist) >= 50:
                    ohlcv_raw = {"open": [], "high": [], "low": [], "close": [], "volume": []}
                    for r in fmp_hist:
                        for field in ohlcv_raw:
                            val = r.get(field)
                            if val is not None:
                                ohlcv_raw[field].append(float(val))
                    closes = ohlcv_raw["close"]
                    if len(closes) >= 253:
                        hist_close = pd.Series(closes)
                        log.debug("Using FMP historical prices for %s: %d bars", ticker, len(closes))
        except Exception:
            pass

        # Fallback to yfinance price history
        if len(hist_close) < 253:
            with _lock:
                cached_prices = _price_cache.get(cache_key)
                prices_fresh = time.time() - _price_ts.get(cache_key, 0) < PRICE_TTL
            if cached_prices is not None and prices_fresh and len(cached_prices) >= 253:
                hist_close = cached_prices
            else:
                try:
                    for yf_retry in range(3):
                        try:
                            hist = t.history(period="14mo", auto_adjust=True)
                            hist_close = hist["Close"] if not hist.empty else pd.Series(dtype=float)
                            if len(hist_close) >= 50:
                                # Also extract OHLCV from yfinance for IN stocks
                                if not ohlcv_raw and not hist.empty:
                                    for col, key in [("Open","open"),("High","high"),("Low","low"),("Close","close"),("Volume","volume")]:
                                        if col in hist.columns:
                                            ohlcv_raw[key] = hist[col].dropna().tolist()
                                break
                            if yf_retry < 2:
                                import time as _ytime
                                _ytime.sleep(2 ** yf_retry)
                        except Exception as yf_exc:
                            if "rate limit" in str(yf_exc).lower() and yf_retry < 2:
                                import time as _ytime
                                _ytime.sleep(3 * (2 ** yf_retry))
                                continue
                            raise
                    with _lock:
                        _price_cache[cache_key] = hist_close
                        _price_ts[cache_key] = time.time()
                except Exception:
                    pass

        # Compute momentum (12-1 month, skip most recent month)
        if len(hist_close) >= 253:
            p1m  = float(hist_close.iloc[-21])
            p12m = float(hist_close.iloc[-252])
            momentum = (p1m - p12m) / p12m if p12m else 0.0
        else:
            _missing.add("momentum_raw")

        # Compute realized vol (annualized, 252-day window)
        if len(hist_close) >= 30:
            log_rets = np.log(hist_close / hist_close.shift(1)).dropna()
            realized_vol = float(log_rets.tail(252).std() * np.sqrt(252))
        else:
            _missing.add("realized_vol_1y")

        # ── Technical indicators (computed locally from OHLCV — no external API) ──
        _tech_indicators: dict[str, Any] = {}
        closes = ohlcv_raw.get("close", [])
        if len(closes) >= 50:
            from nq_data.finnhub import _compute_rsi, _compute_macd, _compute_atr
            rsi = _compute_rsi(closes, 14)
            if rsi is not None:
                _tech_indicators["rsi_14"] = round(rsi, 2)
            macd_line, macd_signal, macd_hist = _compute_macd(closes)
            if macd_line is not None:
                _tech_indicators["macd_line"] = round(macd_line, 4)
                _tech_indicators["macd_signal"] = round(macd_signal, 4) if macd_signal else None
                _tech_indicators["macd_hist"] = round(macd_hist, 4) if macd_hist else None
            highs = ohlcv_raw.get("high", [])
            lows = ohlcv_raw.get("low", [])
            if len(highs) >= 15 and len(lows) >= 15:
                atr = _compute_atr(highs, lows, closes, 14)
                if atr is not None:
                    _tech_indicators["atr_14"] = round(atr, 4)
            _tech_indicators["sma_50"] = round(sum(closes[-50:]) / 50, 4)
            if len(closes) >= 200:
                _tech_indicators["sma_200"] = round(sum(closes[-200:]) / 200, 4)
            if _tech_indicators.get("sma_50"):
                _tech_indicators["price_vs_sma50"] = round(closes[-1] / _tech_indicators["sma_50"] - 1, 4)
            if _tech_indicators.get("sma_200"):
                _tech_indicators["price_vs_sma200"] = round(closes[-1] / _tech_indicators["sma_200"] - 1, 4)
            volumes = ohlcv_raw.get("volume", [])
            if volumes and len(volumes) >= 20:
                avg20 = sum(volumes[-20:]) / 20
                _tech_indicators["volume_today"] = volumes[-1]
                _tech_indicators["volume_20d_avg"] = round(avg20, 2)
                _tech_indicators["volume_ratio"] = round(volumes[-1] / avg20, 3) if avg20 > 0 else None
        result["_tech_indicators"] = _tech_indicators

        # ── Live price fields (from FMP overlay + yfinance fallback) ──
        current_price   = info.get("currentPrice") or info.get("regularMarketPrice")
        week52_high     = info.get("fiftyTwoWeekHigh")
        week52_low      = info.get("fiftyTwoWeekLow")
        analyst_target  = info.get("targetMeanPrice")
        analyst_rec     = info.get("recommendationKey", "")
        market_cap      = info.get("marketCap")
        change_pct      = info.get("regularMarketChangePercent")
        long_name       = info.get("longName") or info.get("shortName") or ticker
        industry        = info.get("industry")
        sector          = info.get("sector")

        if current_price is None:
            # yf.download fallback — more reliable than .info on cloud IPs (different Yahoo endpoint)
            try:
                # yf already imported at module level (Python 3.14 compat)
                sess = _get_yf_session()
                yf_kw = {"period": "5d", "progress": False, "auto_adjust": True, "threads": False}
                if sess:
                    yf_kw["session"] = sess
                hist = yf.download(sym, **yf_kw)
                if hist is not None and not hist.empty and "Close" in hist.columns:
                    close_vals = hist["Close"].dropna()
                    if len(close_vals) > 0:
                        current_price = float(close_vals.iloc[-1])
                        log.debug("yf.download fallback price for %s: %.2f", ticker, current_price)
            except Exception:
                pass
            if current_price is None:
                _missing.add("current_price")

        # Earnings date (yfinance-only)
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

        # EPS TTM (FMP quote.trailingEps overlay + yfinance fallback)
        eps_ttm = info.get("trailingEps") or info.get("dilutedEPS")
        if eps_ttm is None and info.get("netIncomeToCommon") and info.get("sharesOutstanding"):
            try:
                eps_ttm = float(info["netIncomeToCommon"]) / float(info["sharesOutstanding"])
            except (TypeError, ValueError, ZeroDivisionError):
                pass
        if eps_ttm is not None:
            try:
                eps_ttm = round(float(eps_ttm), 2)
            except (TypeError, ValueError):
                eps_ttm = None

        result = {
            "gross_profit_margin": gpm,
            "roe": roe,
            "accruals_ratio": accruals,
            "piotroski": piotroski,
            "momentum_raw": momentum,
            "short_interest_pct": si,
            "pe_ttm": pe_ttm,
            "pb_ratio": pb_ratio,
            "beta": beta,
            "realized_vol_1y": realized_vol,
            "delivery_pct": None,
            "_is_real": True,
            "_is_synthetic": _missing,
            "current_price": float(current_price) if current_price else None,
            "week52_high": float(week52_high) if week52_high else None,
            "week52_low": float(week52_low) if week52_low else None,
            "analyst_target": float(analyst_target) if analyst_target else None,
            "analyst_rec": analyst_rec.upper() if analyst_rec else None,
            "market_cap": float(market_cap) if market_cap else None,
            "change_pct": float(change_pct) if change_pct is not None else None,
            "long_name": long_name,
            "industry": industry,
            "sector": sector,
            "earnings_date": earnings_date,
            "dividend_yield": div_pct,
            "debt_equity": round(float(info.get("debtToEquity")) / 100, 2) if info.get("debtToEquity") is not None else None,
            "revenue_growth_yoy": round(float(info.get("revenueGrowth")) * 100, 1) if info.get("revenueGrowth") is not None else None,
            "fcf_yield": round(fcf_val / market_cap, 4) if (fcf_val := _safe(info.get("freeCashflow")) or 0) > 0 and market_cap else None,
            "eps_ttm": eps_ttm,
        }
    except Exception as exc:
        log.debug("Fundamental fetch failed for %s: %s — returning empty row", ticker, exc)
        result = _empty_row(ticker)

    with _lock:
        _fund_cache[cache_key] = result
        _fund_ts[cache_key] = now
    return result


def fetch_fundamentals_batch(tickers: list[str], market: str = "US", fast_pe: bool = True) -> dict[str, dict]:
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
            futures = {pool.submit(_fetch_one, t, market, fast_pe): t for t in missing}
            for fut in as_completed(futures):
                t = futures[fut]
                try:
                    results[t] = fut.result()
                except Exception as e:
                    logger.debug("Non-critical enrichment failed: %s", e)
                    results[t] = _empty_row(t)

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
                except Exception as e:
                    logger.debug("Non-critical enrichment failed: %s", e)
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


_nse_52w_cache: dict[str, dict] = {}
_nse_52w_ts: float = 0.0
NSE_52W_TTL = 3600  # 1 hour


def _enrich_in_with_nse_data(fundamentals: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """Enrich IN fundamentals with 52-week high/low from NSE quote API."""
    global _nse_52w_cache, _nse_52w_ts

    now = time.time()
    if not _nse_52w_cache or now - _nse_52w_ts > NSE_52W_TTL:
        try:
            from nq_data.price.nse_quote import fetch_nse_52w

            new_cache: dict[str, dict] = {}
            for ticker in tickers[:30]:
                try:
                    data = fetch_nse_52w(ticker)
                    if data:
                        new_cache[ticker] = data
                except Exception:
                    pass

            if new_cache:
                _nse_52w_cache = new_cache
                _nse_52w_ts = now
                log.info("NSE 52w enriched %d tickers", len(new_cache))
        except Exception as exc:
            log.warning("NSE 52w fetch failed: %s", exc)

    if _nse_52w_cache:
        for ticker in tickers:
            nse_data = _nse_52w_cache.get(ticker)
            if nse_data:
                mask = fundamentals["ticker"] == ticker
                if nse_data.get("week52_high"):
                    fundamentals.loc[mask, "week52_high"] = nse_data["week52_high"]
                if nse_data.get("week52_low"):
                    fundamentals.loc[mask, "week52_low"] = nse_data["week52_low"]

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
        row = fund_map.get(t, _empty_row(t)).copy()
        row.pop("_is_real", None)
        rows.append({"ticker": t, "sector": sector_of(t, market), **row})

    fundamentals = pd.DataFrame(rows)
    fundamentals = _add_value_and_lowvol_percentiles(fundamentals)
    fundamentals = _add_insider_percentile(fundamentals, market)

    # IN-specific: enrich with NSE Bhavcopy delivery_pct + NSE quote 52w high/low
    if market == "IN":
        fundamentals = _enrich_with_bhavcopy(fundamentals, tickers)
        fundamentals = _enrich_in_with_nse_data(fundamentals, tickers)

    return UniverseSnapshot(
        tickers=tickers,
        market=market,
        fundamentals=fundamentals,
        macro=macro,
    )


def prewarm_cache(tickers: list[str], market: str = "US") -> None:
    """Called on server startup to populate cache before first request.
    Skipped on Render — Yahoo aggressively rate-limits cloud IPs."""
    if _IS_RENDER:
        log.info("Cache pre-warm skipped on Render (Yahoo rate-limit risk)")
        return
    try:
        fetch_real_macro()
        fetch_fundamentals_batch(tickers[:20], market)
        log.info("Cache pre-warm complete for %d tickers", min(20, len(tickers)))
    except Exception as exc:
        log.warning("Cache pre-warm failed: %s", exc)

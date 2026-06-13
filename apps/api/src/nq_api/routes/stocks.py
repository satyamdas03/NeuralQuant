import logging
import time
from typing import Literal, Any
import asyncio
import json

import httpx
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

log = logging.getLogger(__name__)

from nq_api.deps import get_signal_engine
from nq_api.config import YAHOO_CHART_URL, YAHOO_QUOTE_URL
from nq_api.schemas import AIScore
from nq_api.score_builder import row_to_ai_score, rank_scores_in_universe
from nq_api.universe import UNIVERSE_BY_MARKET
from nq_api.data_builder import build_real_snapshot, _fund_cache, fetch_real_macro, _get_yf_session
from nq_api.cache import score_cache
from nq_api.cache.snapshot_cache import read_snapshot as _read_stock_snapshot, is_stale
from nq_api.cache.quantfactor_cache import get_quantfactor_scores

# REMOVED: _META_CACHE in-memory dict — replaced by Supabase stock_snapshot table
# All live stock meta now reads from stock_snapshot (30-min TTL, populated by GHA)

router = APIRouter()

_PERIOD_MAP = {
    "1d":  ("1d",  "5m"),
    "5d":  ("5d",  "30m"),
    "1mo": ("1mo", "1d"),
    "3mo": ("3mo", "1d"),
    "1y":  ("1y",  "1d"),
    "5y":  ("5y",  "1wk"),
}

# Period → approximate calendar days for FMP historical-price-eod lookback.
# FMP only returns daily (EOD) bars, so 1d/5d intraday periods get a small
# lookback that the frontend can downsample from.
_FMP_DAYS_MAP = {
    "1d":  5,
    "5d":  10,
    "1mo": 35,
    "3mo": 95,
    "1y":  370,
    "5y":  1850,
}


def _yf_sym(ticker: str, market: str) -> str:
    if market == "IN" and "." not in ticker:
        return ticker + ".NS"
    return ticker


def _normalize_ticker(ticker: str, market: str) -> str:
    """Strip exchange suffixes (.NS, .BO) for cache lookup — cache stores bare tickers."""
    if market == "IN":
        return ticker.upper().replace(".NS", "").replace(".BO", "")
    return ticker.upper()


def _fmt_mcap(mc: float, market: str = "US") -> str:
    # India: Indian convention uses Crores (1 Cr = 10M = 1e7) and Lakh Crores (1 LCr = 1e12)
    if market == "IN":
        if mc >= 1e12: return f"₹{mc/1e12:.2f} LCr"
        if mc >= 1e9:  return f"₹{mc/1e7:,.0f} Cr"
        if mc >= 1e7:  return f"₹{mc/1e7:.1f} Cr"
        return f"₹{mc:,.0f}"
    if mc >= 1e12: return f"${mc/1e12:.2f}T"
    if mc >= 1e9:  return f"${mc/1e9:.1f}B"
    if mc >= 1e6:  return f"${mc/1e6:.0f}M"
    return f"${mc:,.0f}"


@router.get("/{ticker}", response_model=AIScore)
async def get_stock_score(
    ticker: str,
    market: Literal["US", "IN", "GLOBAL"] = Query("US"),
    engine: Any = Depends(get_signal_engine),
) -> AIScore:
    ticker_upper = _normalize_ticker(ticker, market)

    # --- Fast path: read from Supabase score_cache (sub-100ms) ---
    # Tiered: try 5min → 24h → any age → live compute
    cached = None
    try:
        cached = await asyncio.to_thread(
            score_cache.read_one, ticker_upper, market, max_age_seconds=300
        )
        if not cached:
            # Tier 2: stale cache (≤24h) — nightly GHA data
            cached = await asyncio.to_thread(
                score_cache.read_one, ticker_upper, market, max_age_seconds=86400
            )
            if cached:
                log.info("score_cache: serving stale (>5min) for %s/%s", ticker_upper, market)
        if not cached:
            # Tier 3: any age — better than 504
            cached = await asyncio.to_thread(
                score_cache.read_one, ticker_upper, market, max_age_seconds=999999999
            )
            if cached:
                log.warning("score_cache: serving very old data for %s/%s", ticker_upper, market)
    except Exception as e:
        log.warning("score_cache.read_one failed: %s", e)
    if cached:
        # Build AIScore from cache row — use regime_id from cache row itself
        df = pd.DataFrame([cached])
        if "regime_id" not in df.columns or pd.isna(df["regime_id"].iloc[0]):
            df["regime_id"] = 1
        return row_to_ai_score(df.iloc[0], market, score_1_10_override=_score_1_10_from_cache(cached))

    # --- Slow path: live compute with hard timeout (cache miss fallback) ---
    # On Render, yfinance is rate-limited — but single-ticker compute is usually
    # fast enough. Try a lightweight 15s fallback before giving up.
    import os
    on_render = bool(os.environ.get("RENDER"))
    timeout_seconds = 15.0 if on_render else 25.0
    try:
        snapshot = await asyncio.wait_for(
            asyncio.to_thread(build_real_snapshot, [ticker_upper], market),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        log.warning("build_real_snapshot timed out for %s (render=%s)", ticker_upper, on_render)
        if on_render:
            # On Render: return 503 so frontend retry logic kicks in
            raise HTTPException(
                status_code=503,
                detail=f"Score data for {ticker_upper} is being refreshed. Please retry in 1-2 minutes.",
            )
        raise HTTPException(
            status_code=504,
            detail=f"Score cache miss for {ticker_upper}; upstream data source is rate-limited. Please retry in ~60s.",
        )
    except Exception as e:
        log.error("build_real_snapshot failed for %s: %s", ticker_upper, e)
        if on_render:
            raise HTTPException(
                status_code=503,
                detail=f"Score data for {ticker_upper} is being refreshed. Please retry in 1-2 minutes.",
            )
        raise HTTPException(status_code=504, detail=f"Data fetch failed for {ticker_upper}. Try again in 30s.")

    if snapshot is None or snapshot.fundamentals.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")

    result_df = await asyncio.to_thread(engine.compute, snapshot)

    matching = result_df[result_df["ticker"] == ticker_upper]
    if matching.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")

    # BUG-002 fix: rank_scores_in_universe on a 1-row DataFrame always returns
    # percentile=1.0 → score=10 regardless of quality. Use _score_to_1_10
    # (absolute composite → 1-10 mapping) so live-path scores are meaningful.
    from nq_api.score_builder import _score_to_1_10 as _s2t
    composite = float(matching.iloc[0]["composite_score"])
    score_override = _s2t(composite)

    return row_to_ai_score(matching.iloc[0], market, score_1_10_override=score_override)


def _score_1_10_from_cache(row: dict) -> int:
    """Derive a 1-10 score from cached composite_score using the same stretching logic."""
    from nq_api.score_builder import _score_to_1_10
    return _score_to_1_10(float(row.get("composite_score", 0.5)))


# Period → (yahoo-range, yahoo-interval) for direct chart API fallback
_YAHOO_RANGE_MAP = {
    "1d":  ("1d",  "5m"),
    "5d":  ("5d",  "30m"),
    "1mo": ("1mo", "1d"),
    "3mo": ("3mo", "1d"),
    "1y":  ("1y",  "1d"),
    "5y":  ("5y",  "1wk"),
}


def _fmt_chart_date(ts_epoch: int, period: str) -> str:
    """Format an epoch seconds timestamp for the chart x-axis."""
    import datetime as _dt
    dt = _dt.datetime.fromtimestamp(ts_epoch)
    if period in ("1d", "5d"):
        return dt.strftime("%m/%d %H:%M")
    return dt.strftime("%b %d")


def _fetch_chart_fmp(sym: str, period: str, market: str) -> list[dict]:
    """Try FMP historical-price-eod as the primary chart data source.
    Returns [] on any failure (caller should fall back to yfinance)."""
    try:
        from nq_data.fmp import get_fmp_client
        fmp = get_fmp_client()
        if not fmp._enabled:
            return []

        days = _FMP_DAYS_MAP.get(period, 35)
        fmp_data = fmp.get_historical_prices(sym, days=days)
        if not fmp_data or not isinstance(fmp_data, list) or len(fmp_data) == 0:
            return []

        # FMP returns daily bars — for intraday periods (1d, 5d) we still
        # serve daily bars (frontend gracefully handles this).  Convert to
        # the chart dict format expected by the frontend.
        out: list[dict] = []
        for row in fmp_data:
            try:
                dt_str = row.get("date")
                if not dt_str:
                    continue
                # FMP date format: "2024-01-15" → format to "Jan 15"
                import datetime as _dt
                dt = _dt.datetime.strptime(str(dt_str)[:10], "%Y-%m-%d")
                if period in ("1d", "5d"):
                    date_str = dt.strftime("%m/%d %H:%M")
                else:
                    date_str = dt.strftime("%b %d")

                close = row.get("close")
                open_ = row.get("open")
                high = row.get("high")
                low = row.get("low")
                vol = row.get("volume", 0)

                if close is None or open_ is None:
                    continue

                out.append({
                    "date":   date_str,
                    "close":  round(float(close), 2),
                    "open":   round(float(open_), 2),
                    "high":   round(float(high), 2) if high is not None else round(float(close), 2),
                    "low":    round(float(low), 2) if low is not None else round(float(close), 2),
                    "volume": int(vol) if vol else 0,
                })
            except Exception as row_exc:
                log.debug("FMP chart row parse failed for %s: %s", sym, row_exc)
                continue
        return out
    except Exception as exc:
        log.warning("FMP chart fetch failed for %s (%s): %s", sym, period, exc)
        return []


def _fetch_chart_yahoo_direct(sym: str, period: str) -> list[dict]:
    """Hit Yahoo's chart API directly (v8) — works when yfinance's scraping path fails
    in cloud environments (Render, etc.). Returns [] on any error."""
    from nq_api.config import YAHOO_CHART_URL
    yrange, yinterval = _YAHOO_RANGE_MAP.get(period, ("1mo", "1d"))
    url = f"{YAHOO_CHART_URL}/{sym}"
    params = {"range": yrange, "interval": yinterval, "includePrePost": "false"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
    }
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            r = client.get(url, params=params, headers=headers)
            r.raise_for_status()
            j = r.json()
    except Exception as e:
        log.warning("yahoo-direct chart fetch failed for %s: %s", sym, e)
        return []

    try:
        result = j["chart"]["result"][0]
        timestamps = result.get("timestamp") or []
        quote = result["indicators"]["quote"][0]
        opens   = quote.get("open")   or []
        highs   = quote.get("high")   or []
        lows    = quote.get("low")    or []
        closes  = quote.get("close")  or []
        volumes = quote.get("volume") or []
    except Exception as e:
        log.warning("yahoo-direct parse failed for %s: %s", sym, e)
        return []

    out: list[dict] = []
    for i, ts in enumerate(timestamps):
        try:
            c = closes[i] if i < len(closes) else None
            o = opens[i]  if i < len(opens)  else None
            h = highs[i]  if i < len(highs)  else None
            lo = lows[i]  if i < len(lows)   else None
            v = volumes[i] if i < len(volumes) else 0
            if c is None or o is None:
                continue
            out.append({
                "date":   _fmt_chart_date(int(ts), period),
                "close":  round(float(c),  2),
                "open":   round(float(o),  2),
                "high":   round(float(h),  2) if h is not None else round(float(c), 2),
                "low":    round(float(lo), 2) if lo is not None else round(float(c), 2),
                "volume": int(v or 0),
            })
        except Exception as e:
            log.debug("Non-critical enrichment failed: %s", e)
            continue
    return out


@router.get("/{ticker}/chart")
async def get_stock_chart(
    ticker: str,
    period: str = Query("1mo"),
    market: str = Query("US"),
):
    yf_period, interval = _PERIOD_MAP.get(period, ("1mo", "1d"))
    sym = _yf_sym(ticker.upper(), market)
    data: list[dict] = []

    # ── Primary path: FMP historical-price-eod (fast, reliable, cloud-friendly) ──
    data = await asyncio.to_thread(_fetch_chart_fmp, sym, period, market)

    # ── Fallback 1: yfinance (offloaded to thread pool) ──
    if not data:
        log.info("chart fallback: yfinance for %s (%s)", sym, period)

        def _fetch_chart():
            d: list[dict] = []
            try:
                hist = yf.Ticker(sym, session=_get_yf_session()).history(period=yf_period, interval=interval, auto_adjust=True)
                if hist is not None and not hist.empty:
                    for idx, row in hist.iterrows():
                        try:
                            if period in ("1d", "5d"):
                                date_str = idx.strftime("%m/%d %H:%M")
                            else:
                                date_str = idx.strftime("%b %d")
                            d.append({
                                "date":   date_str,
                                "close":  round(float(row["Close"]), 2),
                                "open":   round(float(row["Open"]),  2),
                                "high":   round(float(row["High"]),  2),
                                "low":    round(float(row["Low"]),   2),
                                "volume": int(row.get("Volume") or 0),
                            })
                        except Exception as row_exc:
                            log.debug("chart row parse failed for %s: %s", sym, row_exc)
                            continue
            except Exception as exc:
                log.warning("yfinance chart failed for %s (%s) — will try Yahoo direct: %s",
                            sym, period, exc)
            return d

        data = await asyncio.to_thread(_fetch_chart)

    # ── Fallback 2: Yahoo chart API directly (last resort) ──
    if not data:
        log.info("chart fallback: yahoo-direct for %s (%s)", sym, period)
        data = await asyncio.to_thread(_fetch_chart_yahoo_direct, sym, period)

    if not data:
        # Return valid empty-shape JSON rather than 500 so the UI can display
        # "No chart data" gracefully without a crash.
        return {
            "ticker": ticker.upper(),
            "period": period,
            "data": [],
            "period_change_pct": 0.0,
        }

    period_change = 0.0
    if len(data) >= 2:
        first = data[0]["close"]
        last  = data[-1]["close"]
        period_change = round((last - first) / first * 100, 2) if first else 0.0

    return {
        "ticker": ticker.upper(),
        "period": period,
        "data": data,
        "period_change_pct": period_change,
    }


_NULL_FIELDS = ("market_cap", "pe_ttm", "pb_ratio", "beta", "week_52_high", "week_52_low",
                 "earnings_date", "analyst_target", "analyst_recommendation",
                 "dividend_yield", "industry", "sector", "current_price")

# Enrichment fields that MUST be present for cached data to be considered complete.
# If any of these are missing, the cache is from a pre-enrichment version and must be refreshed.
_ENRICHMENT_FIELDS = ("altman_z_score", "insider_buys", "dividend_yield_pct", "dcf_value")

# Numeric fields where 0 / 0.0 is a sentinel for "missing" — never a real value for a listed stock
_NUMERIC_NULL_SENTINELS = {
    "market_cap", "pe_ttm", "pb_ratio", "beta",
    "week_52_high", "week_52_low", "current_price", "analyst_target",
}


def _is_nullish(meta: dict, key: str) -> bool:
    v = meta.get(key)
    if v is None:
        return True
    if key in _NUMERIC_NULL_SENTINELS and v == 0:
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    return False


def _has_null_fields(meta: dict) -> bool:
    """Check if critical fields are null (or 0-sentinel) in a meta dict.
    Only requires enrichment fields when the data explicitly claims to be enriched
    (e.g., from the enrichment pipeline). Score_cache rows don't have these,
    but are still valid if core fields are present."""
    if any(_is_nullish(meta, k) for k in _NULL_FIELDS):
        return True
    # Only require enrichment fields if the data explicitly contains them
    has_enrichment_claim = any(k in meta for k in _ENRICHMENT_FIELDS)
    if has_enrichment_claim:
        enrichment_values = [meta.get(k) for k in _ENRICHMENT_FIELDS if k in meta]
        if not enrichment_values or all(v is None for v in enrichment_values):
            return True
    return False


def _merge_meta(base: dict, overlay: dict) -> dict:
    """Merge overlay into base: overlay values replace nulls / 0-sentinels in base."""
    merged = {**base}
    for k, v in overlay.items():
        if _is_nullish(merged, k) and v is not None:
            # Don't overwrite with another 0 sentinel
            if isinstance(v, (int, float)) and v == 0 and k in _NUMERIC_NULL_SENTINELS:
                continue
            merged[k] = v
    return merged


_META_TIMEOUT = 15  # seconds — hard cap for meta enrichment; return partial on timeout


@router.get("/{ticker}/meta")
async def get_stock_meta(ticker: str, market: str = Query("US")):
    """Return stock metadata. Reads from stock_snapshot (30-min TTL) first.
    On miss/stale, falls back to FMP direct with 8s timeout."""
    t_up = _normalize_ticker(ticker, market)

    # ── Phase 1: stock_snapshot (serve even if stale — partial data > no data) ──
    snap = None
    try:
        snap = await asyncio.wait_for(
            asyncio.to_thread(_read_stock_snapshot, t_up, market),
            timeout=8.0,
        )
    except Exception:
        pass

    if snap:
        try:
            meta = _snapshot_to_meta(snap)
        except Exception as e:
            log.warning("_snapshot_to_meta failed for %s: %s", t_up, e)
            meta = _empty_meta(t_up)
        # Attempt enrichment from FMP (non-critical)
        try:
            fmp_extra = await asyncio.wait_for(
                asyncio.to_thread(_fetch_stock_meta_fmp_light, t_up, market),
                timeout=8.0,
            )
            if isinstance(fmp_extra, dict):
                meta = _merge_meta(meta, fmp_extra)
        except Exception:
            pass
        # If key fields still missing after FMP, try yfinance gap-fill
        _CRITICAL_FIELDS = ("pe_ttm", "pb_ratio", "week_52_high", "week_52_low",
                            "analyst_target", "analyst_recommendation", "dividend_yield")
        missing = [f for f in _CRITICAL_FIELDS if meta.get(f) is None]
        if missing:
            try:
                yf_meta = await asyncio.wait_for(
                    asyncio.to_thread(_fetch_stock_meta, t_up, market),
                    timeout=10.0,
                )
                if isinstance(yf_meta, dict):
                    for f in missing:
                        yf_val = yf_meta.get(f)
                        if yf_val is not None:
                            meta[f] = yf_val
                    if meta.get("earnings_date") is None and yf_meta.get("earnings_date"):
                        meta["earnings_date"] = yf_meta["earnings_date"]
            except (asyncio.TimeoutError, Exception):
                log.debug("meta yfinance gap-fill failed for %s (non-critical)", t_up)
        return _ensure_price(meta, t_up, market)

    # ── Phase 2: FMP direct fallback ───────────────────────────────────
    fmp_meta = None
    try:
        fmp_meta = await asyncio.wait_for(
            asyncio.to_thread(_fetch_stock_meta_fmp, t_up, market),
            timeout=15.0,
        )
        if isinstance(fmp_meta, dict):
            # Check if key fields are missing — if so, try yfinance to fill gaps
            _MISSING_FIELDS = ("pe_ttm", "pb_ratio", "week_52_high", "week_52_low",
                               "analyst_target", "analyst_recommendation", "dividend_yield")
            missing = [f for f in _MISSING_FIELDS if fmp_meta.get(f) is None]
            if not missing:
                return _ensure_price(fmp_meta, t_up, market)
            # FMP returned partial data — try yfinance to fill the gaps
            log.info("meta FMP partial for %s, missing: %s — trying yfinance gap-fill", t_up, missing)
            try:
                yf_meta = await asyncio.wait_for(
                    asyncio.to_thread(_fetch_stock_meta, t_up, market),
                    timeout=10.0,
                )
                if isinstance(yf_meta, dict):
                    for f in missing:
                        yf_val = yf_meta.get(f)
                        if yf_val is not None:
                            fmp_meta[f] = yf_val
                    # Also fill earnings_date if missing
                    if fmp_meta.get("earnings_date") is None and yf_meta.get("earnings_date"):
                        fmp_meta["earnings_date"] = yf_meta["earnings_date"]
            except (asyncio.TimeoutError, Exception):
                log.debug("meta yfinance gap-fill failed for %s (non-critical)", t_up)
            return _ensure_price(fmp_meta, t_up, market)
    except asyncio.TimeoutError:
        log.warning("meta FMP timed out for %s", t_up)

    # ── Phase 3: yfinance fallback (last resort, all markets) ─────────
    try:
        yf_meta = await asyncio.wait_for(
            asyncio.to_thread(_fetch_stock_meta, t_up, market),
            timeout=10.0,
        )
        if isinstance(yf_meta, dict):
            return _ensure_price(yf_meta, t_up, market)
    except asyncio.TimeoutError:
        log.warning("meta yfinance timed out for %s", t_up)

    log.error("meta all sources failed for %s", t_up)
    return _empty_meta(t_up)


def _ensure_price(meta: dict, ticker: str, market: str) -> dict:
    """Backfill current_price via the reliable openbb->snapshot->score_cache chain
    when the meta path left it null (e.g. yfinance blocked on Render)."""
    if isinstance(meta, dict) and meta.get("current_price") is None:
        try:
            from nq_api.services.live_price import get_live_price
            lp, _src = get_live_price(ticker, market)
            if lp:
                meta["current_price"] = round(float(lp), 2)
        except Exception:
            pass
    return meta


def _safe_round(v, decimals: int) -> float | None:
    if v is None:
        return None
    try:
        return round(float(v), decimals)
    except (TypeError, ValueError):
        return None


def _snapshot_to_meta(snap: dict) -> dict:
    """Convert a stock_snapshot row to the legacy meta dict shape."""
    mc = snap.get("market_cap")
    price = snap.get("price")
    return {
        "ticker": snap.get("ticker", ""),
        "name": snap.get("company_name") or snap.get("ticker", ""),
        "market_cap": mc,
        "market_cap_fmt": _fmt_mcap(float(mc), snap.get("market", "US")) if mc else None,
        "pe_ttm": _safe_round(snap.get("pe_ttm"), 1),
        "pb_ratio": _safe_round(snap.get("pb_ratio"), 2),
        "beta": _safe_round(snap.get("beta"), 2),
        "week_52_high": _safe_round(snap.get("week_52_high"), 2),
        "week_52_low": _safe_round(snap.get("week_52_low"), 2),
        "earnings_date": snap.get("earnings_date"),
        "analyst_target": _safe_round(snap.get("analyst_target"), 2),
        "analyst_recommendation": snap.get("recommendation"),
        "sector": snap.get("sector"),
        "industry": snap.get("sub_sector"),
        "dividend_yield": None,  # not in snapshot yet
        "current_price": _safe_round(price, 2),
        "change_pct": _safe_round(snap.get("change_pct"), 2),
        "volume": snap.get("volume"),
        "rsi_14d": _safe_round(snap.get("rsi_14d"), 1),
        "cached_at": snap.get("cached_at"),
        "stale": snap.get("stale", False),
    }


def _read_score_cache(ticker: str, market: str) -> dict | None:
    """Read score_cache row and convert to meta-compatible dict."""
    try:
        sc = score_cache.read_one(ticker, market, max_age_seconds=999999999)
        if sc:
            return _build_from_score_cache(ticker, market, sc)
    except Exception:
        pass
    return None


def _build_from_score_cache(ticker: str, market: str, sc: dict) -> dict | None:
    """Build a meta dict from a score_cache row."""
    if not sc:
        return None
    mc = sc.get("market_cap")
    pe = sc.get("pe_ttm")
    pb = sc.get("pb_ratio")
    hi52 = sc.get("week52_high")
    lo52 = sc.get("week52_low")
    tgt = sc.get("analyst_target")
    cur = sc.get("current_price")
    sec = sc.get("sector")
    beta_v = sc.get("beta")
    return {
        "ticker": ticker,
        "name": sc.get("long_name") or ticker,
        "market_cap": mc,
        "market_cap_fmt": _fmt_mcap(float(mc), market) if mc else None,
        "pe_ttm": round(float(pe), 1) if pe is not None else None,
        "pb_ratio": round(float(pb), 2) if pb is not None else None,
        "beta": round(float(beta_v), 2) if beta_v is not None else None,
        "week_52_high": hi52,
        "week_52_low": lo52,
        "earnings_date": sc.get("earnings_date"),
        "analyst_target": tgt,
        "analyst_recommendation": sc.get("analyst_rec"),
        "sector": sec,
        "industry": sc.get("industry"),
        "dividend_yield": sc.get("dividend_yield"),
        "current_price": cur,
    }


def _empty_meta(ticker: str) -> dict:
    """Minimal response when all sources fail."""
    return {
        "ticker": ticker,
        "name": ticker,
        "market_cap": None, "market_cap_fmt": None,
        "pe_ttm": None, "pb_ratio": None, "beta": None,
        "week_52_high": None, "week_52_low": None,
        "earnings_date": None, "analyst_target": None, "analyst_recommendation": None,
        "sector": None, "industry": None, "dividend_yield": None,
        "current_price": None,
    }


def _persist_meta(ticker: str, market: str, data: dict) -> None:
    """Persist stock meta to Supabase for cold-start resilience."""
    import json as _json
    from nq_api.cache.score_cache import _supabase_rest, _sanitize_floats
    from datetime import datetime, timezone

    try:
        # Sanitize NaN/Inf before JSON serialization (data may contain NaN from yfinance)
        safe_data = _sanitize_floats(data)
        row = {
            "ticker": ticker,
            "market": market,
            "data": _json.dumps(safe_data),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        # Upsert: insert new or update existing for this ticker+market
        _supabase_rest(
            "stock_meta",
            method="PATCH",
            body=[row],
            query={"ticker": f"eq.{ticker}", "market": f"eq.{market}"},
        )
    except Exception as e:
        log.debug("Non-critical enrichment failed: %s", e)
        # Try INSERT if PATCH fails (row doesn't exist yet)
        try:
            _supabase_rest("stock_meta", method="POST", body=[row])
        except Exception:
            log.debug("meta persist to Supabase failed (non-critical)")


def _fetch_stock_meta_yahoo_direct(ticker: str, market: str) -> dict | Exception:
    """Yahoo quoteSummary v10 — direct HTTP fallback when yfinance is rate-limited.
    Returns a dict with the same shape as `_fetch_stock_meta`, or an Exception."""
    sym = _yf_sym(ticker, market)
    modules = (
        "summaryDetail,defaultKeyStatistics,financialData,"
        "assetProfile,calendarEvents,price"
    )
    url = f"{YAHOO_QUOTE_URL}/{sym}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
    }
    last_exc: Exception | None = None
    for attempt in range(2):  # 2 attempts: initial + 1 retry
        try:
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                r = client.get(url, params={"modules": modules}, headers=headers)
                r.raise_for_status()
                j = r.json()
                break  # success — exit retry loop
        except Exception as exc:
            last_exc = exc
            if attempt < 1:
                import time as _t
                _t.sleep(1)  # brief pause before retry
    else:
        # Both attempts failed
        return last_exc or Exception("Yahoo direct fallback failed")

    try:
        result = j["quoteSummary"]["result"][0]
    except Exception as exc:
        return exc

    def _raw(d, *path):
        cur = d
        for p in path:
            if not isinstance(cur, dict) or p not in cur:
                return None
            cur = cur[p]
        if isinstance(cur, dict) and "raw" in cur:
            return cur["raw"]
        return cur

    summary = result.get("summaryDetail", {})
    stats   = result.get("defaultKeyStatistics", {})
    fin     = result.get("financialData", {})
    prof    = result.get("assetProfile", {})
    cal     = result.get("calendarEvents", {})
    price   = result.get("price", {})

    mc        = _raw(price, "marketCap") or _raw(summary, "marketCap")
    pe_ttm    = _raw(summary, "trailingPE")
    pb_ratio  = _raw(stats, "priceToBook")
    beta_v    = _raw(summary, "beta") or _raw(stats, "beta")
    hi_52     = _raw(summary, "fiftyTwoWeekHigh")
    lo_52     = _raw(summary, "fiftyTwoWeekLow")
    tgt_mean  = _raw(fin, "targetMeanPrice")
    rec       = fin.get("recommendationKey") if isinstance(fin, dict) else None
    sector    = prof.get("sector") if isinstance(prof, dict) else None
    industry  = prof.get("industry") if isinstance(prof, dict) else None
    cur_price = _raw(price, "regularMarketPrice") or _raw(fin, "currentPrice")
    long_name = price.get("longName") or price.get("shortName") or ticker

    # Earnings date
    earnings_date = None
    try:
        ed_list = cal.get("earnings", {}).get("earningsDate", []) if isinstance(cal, dict) else []
        if ed_list:
            ts = ed_list[0].get("raw") if isinstance(ed_list[0], dict) else None
            if ts:
                import datetime as _dt
                earnings_date = _dt.datetime.utcfromtimestamp(int(ts)).date().isoformat()
    except Exception:
        pass

    # Dividend yield
    div_pct = None
    div_rate = _raw(summary, "dividendRate")
    if div_rate and cur_price:
        try:
            v = float(div_rate) / float(cur_price) * 100
            if 0 < v < 20:
                div_pct = round(v, 2)
        except Exception:
            pass
    if div_pct is None:
        div_raw = _raw(summary, "dividendYield")
        if div_raw:
            try:
                v = float(div_raw)
                v = v if v > 1 else v * 100
                if 0 < v < 20:
                    div_pct = round(v, 2)
            except Exception:
                pass

    return {
        "ticker":                  ticker,
        "name":                    long_name,
        "market_cap":              mc,
        "market_cap_fmt":          _fmt_mcap(float(mc), market) if mc is not None else None,
        "pe_ttm":                  round(float(pe_ttm), 1)  if pe_ttm   is not None else None,
        "pb_ratio":                round(float(pb_ratio), 2) if pb_ratio is not None else None,
        "beta":                    round(float(beta_v), 2)  if beta_v  is not None else None,
        "week_52_high":            hi_52,
        "week_52_low":             lo_52,
        "earnings_date":           earnings_date,
        "analyst_target":          tgt_mean,
        "analyst_recommendation":  rec,
        "sector":                  sector,
        "industry":                industry,
        "dividend_yield":          div_pct,
        "current_price":           cur_price,
    }


def _fetch_stock_meta_fmp(ticker: str, market: str) -> dict | Exception:
    """FMP-first stock meta: profile + quote + key_metrics + ratios.
    Returns dict on success, Exception on failure."""
    try:
        from nq_data.fmp import get_fmp_client
        fmp = get_fmp_client()
        if not fmp._enabled:
            return Exception("FMP disabled (no API key)")

        sym = _yf_sym(ticker, market)
        profile = fmp.get_profile(sym)
        quote = fmp.get_quote(sym)
        metrics = fmp.get_key_metrics(sym)
        ratios = fmp.get_ratios(sym)

        if not profile and not quote:
            return Exception(f"FMP returned no data for {ticker}")

        # Build meta dict from FMP sources
        mc = None
        pe_ttm = None
        pb_ratio = None
        beta_v = None
        div_pct = None
        current_price = None
        hi52 = None
        lo52 = None
        name = ticker
        sector = None
        industry = None

        if quote:
            current_price = quote.get("price")
            mc = quote.get("market_cap")
            hi52 = quote.get("year_high")
            lo52 = quote.get("year_low")

        if profile:
            name = profile.get("name") or name
            sector = profile.get("sector")
            industry = profile.get("industry")
            if not mc:
                mc = profile.get("market_cap")
            # Beta is available in profile response
            if profile.get("beta") is not None:
                beta_v = profile.get("beta")

        if metrics:
            m_pb = metrics.get("pb_ratio")
            if m_pb is not None:
                pb_ratio = m_pb
            m_beta = metrics.get("beta")
            if m_beta is not None and beta_v is None:
                beta_v = m_beta
            m_div = metrics.get("dividend_yield")
            if m_div is not None:
                try:
                    v = float(m_div)
                    div_pct = round(v * 100, 2) if v < 1 else round(v, 2)
                except (TypeError, ValueError):
                    pass

        # Ratios endpoint provides P/B (more reliable than key_metrics)
        if ratios:
            r_pb = ratios.get("price_to_book")
            if r_pb is not None:
                pb_ratio = r_pb

        # Calculate P/E from FMP price + income statement EPS
        # FMP /stable/ doesn't include P/E directly — compute it for reliability
        fmp_price = current_price
        if not fmp_price and profile and profile.get("price"):
            fmp_price = float(profile["price"])
        if fmp_price and float(fmp_price) > 0:
            income = fmp.get_income_statement(sym)
            if income and income.get("eps"):
                try:
                    pe_calc = round(float(fmp_price) / float(income["eps"]), 1)
                    if 0.5 < pe_calc < 5000:  # sanity bounds
                        pe_ttm = pe_calc
                except (TypeError, ValueError, ZeroDivisionError):
                    pass

        # Normalize numeric fields
        if pe_ttm is not None:
            try:
                pe_ttm = round(float(pe_ttm), 1)
            except (TypeError, ValueError):
                pe_ttm = None
        if pb_ratio is not None:
            try:
                pb_ratio = round(float(pb_ratio), 2)
            except (TypeError, ValueError):
                pb_ratio = None
        if beta_v is not None:
            try:
                beta_v = round(float(beta_v), 2)
            except (TypeError, ValueError):
                beta_v = None

        meta = {
            "ticker": ticker,
            "name": name,
            "market_cap": mc,
            "market_cap_fmt": _fmt_mcap(float(mc), market) if mc else None,
            "pe_ttm": pe_ttm,
            "pb_ratio": pb_ratio,
            "beta": beta_v,
            "week_52_high": hi52,
            "week_52_low": lo52,
            "earnings_date": None,  # filled below from FMP calendar
            "analyst_target": None,  # filled below from FMP price target
            "analyst_recommendation": None,  # filled below from FMP grades
            "sector": sector,
            "industry": industry,
            "dividend_yield": div_pct,
            "current_price": current_price,
        }

        # Post-build FMP enrichment: analyst target, grades, earnings, dividends, insider
        # Run independent enrichment calls IN PARALLEL to reduce latency from ~16s → ~3s
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            from datetime import date as _date, timedelta as _td

            today = _date.today()
            enrichment_results: dict[str, Any] = {}

            def _safe_call(key: str, fn, *args, **kwargs):
                """Run an FMP call, return (key, result) on success, (key, None) on failure."""
                try:
                    return (key, fn(*args, **kwargs))
                except Exception:
                    return (key, None)

            with ThreadPoolExecutor(max_workers=6) as pool:
                futures = {
                    pool.submit(_safe_call, "target", fmp.get_price_target, sym): "target",
                    pool.submit(_safe_call, "grades", fmp.get_analyst_grades, sym): "grades",
                    pool.submit(_safe_call, "earnings", fmp.get_earnings_calendar,
                                today.isoformat(), (today + _td(days=30)).isoformat()): "earnings",
                    pool.submit(_safe_call, "divs", fmp.get_dividends, sym): "divs",
                    pool.submit(_safe_call, "estimates", fmp.get_analyst_estimates, sym): "estimates",
                    pool.submit(_safe_call, "scores", fmp.get_financial_scores, sym): "scores",
                    pool.submit(_safe_call, "insider", fmp.get_insider_trading, sym): "insider",
                    pool.submit(_safe_call, "dcf", fmp.get_dcf, sym): "dcf",
                }
                for future in as_completed(futures, timeout=10.0):
                    key = futures[future]
                    try:
                        _, result = future.result()
                        enrichment_results[key] = result
                    except Exception:
                        enrichment_results[key] = None

            # Apply results to meta dict
            tgt = enrichment_results.get("target")
            if tgt and isinstance(tgt, dict) and tgt.get("target_avg") is not None:
                meta["analyst_target"] = round(float(tgt["target_avg"]), 2)

            grades = enrichment_results.get("grades")
            if grades and isinstance(grades, dict) and grades.get("consensus"):
                meta["analyst_recommendation"] = grades["consensus"]

            earnings = enrichment_results.get("earnings")
            if earnings and isinstance(earnings, list):
                ticker_earnings = [
                    e for e in earnings
                    if e.get("ticker", "").upper() == ticker.upper()
                    or e.get("ticker", "").upper() == sym.upper()
                ]
                if ticker_earnings and ticker_earnings[0].get("date"):
                    meta["earnings_date"] = ticker_earnings[0]["date"]

            divs = enrichment_results.get("divs")
            if divs and isinstance(divs, list) and divs:
                meta["dividend_history"] = divs[:4]

            estimates = enrichment_results.get("estimates")
            if estimates and isinstance(estimates, dict):
                if estimates.get("revenue_estimate") is not None:
                    meta["analyst_revenue_est"] = float(estimates["revenue_estimate"])
                if estimates.get("eps_estimate") is not None:
                    meta["analyst_eps_est"] = float(estimates["eps_estimate"])

            scores = enrichment_results.get("scores")
            if scores and isinstance(scores, dict):
                if scores.get("altman_z_score") is not None:
                    meta["altman_z_score"] = round(float(scores["altman_z_score"]), 2)
                if scores.get("piotroski_score") is not None:
                    meta["piotroski_score"] = int(scores["piotroski_score"])

            insider = enrichment_results.get("insider")
            if insider and isinstance(insider, list):
                buys = sum(1 for t in insider if "Buy" in str(t.get("transaction_type", "")))
                sells = sum(1 for t in insider if "Sell" in str(t.get("transaction_type", "")))
                meta["insider_buys"] = buys
                meta["insider_sells"] = sells

            dcf = enrichment_results.get("dcf")
            if dcf and isinstance(dcf, dict) and dcf.get("dcf_value") is not None:
                meta["dcf_value"] = round(float(dcf["dcf_value"]), 2)
                if dcf.get("stock_price") is not None:
                    meta["dcf_stock_price"] = round(float(dcf["stock_price"]), 2)
        except Exception as exc:
            log.debug("FMP post-build enrichment failed for %s: %s", ticker, exc)

        # ── OpenBB enrichment (supplementary data) ──────────────────────────
        try:
            from nq_data.openbb import get_openbb_client
            obb = get_openbb_client()
            if obb.enabled:
                obb_sym = _yf_sym(ticker, market) if market == "IN" else ticker

                # Dividend history — calculate trailing yield from recent dividends
                divs = obb.get_dividends(obb_sym)
                if divs and isinstance(divs, list) and len(divs) > 0:
                    if not meta.get("dividend_yield_pct"):
                        # Sum last 4 quarterly dividends for trailing annual yield
                        recent = sorted(divs, key=lambda d: d.get("ex_dividend_date", ""), reverse=True)[:4]
                        annual_div = sum(float(d.get("amount", 0)) for d in recent)
                        price = meta.get("current_price") or meta.get("previous_close")
                        if annual_div > 0 and price and price > 0:
                            meta["dividend_yield_pct"] = round((annual_div / price) * 100, 2)

                # Analyst consensus — target prices, recommendation, number of analysts
                consensus = obb.get_consensus(obb_sym)
                if consensus and isinstance(consensus, dict):
                    if not meta.get("analyst_consensus") and consensus.get("recommendation"):
                        meta["analyst_consensus"] = consensus["recommendation"]
                    if not meta.get("analyst_target") and consensus.get("target_consensus"):
                        meta["analyst_target"] = round(float(consensus["target_consensus"]), 2)
                    meta["analyst_count"] = consensus.get("number_of_analysts")

                # Share statistics — institutional ownership, short interest
                ownership = obb.get_ownership(obb_sym)
                if ownership and isinstance(ownership, dict):
                    meta["shares_outstanding"] = ownership.get("outstanding_shares")
                    meta["float_shares"] = ownership.get("float_shares")
                    if ownership.get("short_percent_of_float"):
                        meta["short_pct_float"] = round(float(ownership["short_percent_of_float"]) * 100, 2)

                # Yield curve for macro context
                yc = obb.get_yield_curve()
                if yc and isinstance(yc, list):
                    yc_map = {p.get("maturity"): p.get("rate") for p in yc if isinstance(p, dict)}
                    if yc_map.get("year_2"):
                        meta["yield_curve_2y"] = round(float(yc_map["year_2"]) * 100, 2)
                    if yc_map.get("year_10"):
                        meta["yield_curve_10y"] = round(float(yc_map["year_10"]) * 100, 2)
                    if yc_map.get("year_2") and yc_map.get("year_10"):
                        meta["yield_curve_spread"] = round((float(yc_map["year_10"]) - float(yc_map["year_2"])) * 100, 2)
        except Exception as exc:
            log.debug("OpenBB enrichment failed for %s: %s", ticker, exc)

        return meta
    except Exception as exc:
        return exc


def _fetch_stock_meta(ticker: str, market: str) -> dict | Exception:
    """Blocking yfinance calls — run in thread pool."""
    sym = _yf_sym(ticker, market)
    try:
        t = yf.Ticker(sym, session=_get_yf_session())
        info = t.info or {}

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

        mc = info.get("marketCap")

        # Dividend yield: yfinance dividendYield is decimal (0.005 = 0.5%).
        # Some versions return already-percent — cross-check with dividendRate / currentPrice.
        div_pct = None
        div_rate = info.get("dividendRate")
        price_now = info.get("currentPrice") or info.get("regularMarketPrice")
        if div_rate and price_now:
            try:
                div_pct = round(float(div_rate) / float(price_now) * 100, 2)
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

        # yf.download fallback — more reliable than .info on cloud IPs (different Yahoo endpoint)
        if price_now is None:
            try:
                hist = yf.download(sym, period="5d", progress=False, auto_adjust=True, threads=False)
                if hist is not None and not hist.empty and "Close" in hist.columns:
                    close_vals = hist["Close"].dropna()
                    if len(close_vals) > 0:
                        price_now = float(close_vals.iloc[-1])
            except Exception:
                pass

        return {
            "ticker":                  ticker,
            "name":                    info.get("longName") or info.get("shortName") or ticker,
            "market_cap":              mc,
            "market_cap_fmt":          _fmt_mcap(float(mc), market) if mc is not None else None,
            "pe_ttm":                  round(float(info["trailingPE"]), 1)  if info.get("trailingPE")    else None,
            "pb_ratio":                round(float(info["priceToBook"]), 2) if info.get("priceToBook")   else None,
            "beta":                    round(float(info["beta"]), 2)        if info.get("beta")          else None,
            "week_52_high":            info.get("fiftyTwoWeekHigh"),
            "week_52_low":             info.get("fiftyTwoWeekLow"),
            "earnings_date":           earnings_date,
            "analyst_target":          info.get("targetMeanPrice"),
            "analyst_recommendation":  info.get("recommendationKey"),
            "sector":                  info.get("sector"),
            "industry":                info.get("industry"),
            "dividend_yield":          div_pct,
            "current_price":           price_now,
        }
    except Exception as exc:
        return exc


def _fetch_stock_meta_fmp_light(ticker: str, market: str) -> dict | None:
    """Lightweight FMP fetch for fields NOT in stock_snapshot.
    Returns dict with earnings_date, analyst_target, recommendation, dividend_yield.
    Returns None on failure (non-critical)."""
    try:
        from nq_data.fmp import get_fmp_client
        from datetime import date as _date, timedelta as _td
        fmp = get_fmp_client()
        if not fmp._enabled:
            return None
        sym = _yf_sym(ticker, market)
        extras = {}

        # Analyst target
        tgt = fmp.get_price_target(sym)
        if tgt and tgt.get("target_avg") is not None:
            extras["analyst_target"] = round(float(tgt["target_avg"]), 2)

        # Analyst consensus
        grades = fmp.get_analyst_grades(sym)
        if grades and grades.get("consensus"):
            extras["analyst_recommendation"] = grades["consensus"]

        # Earnings date (next 30 days)
        today = _date.today()
        earnings = fmp.get_earnings_calendar(today.isoformat(), (today + _td(days=30)).isoformat())
        if earnings and isinstance(earnings, list):
            ticker_earnings = [
                e for e in earnings
                if e.get("ticker", "").upper() == ticker.upper()
                or e.get("ticker", "").upper() == sym.upper()
            ]
            if ticker_earnings and ticker_earnings[0].get("date"):
                extras["earnings_date"] = ticker_earnings[0]["date"]

        # Dividend history (latest 4)
        divs = fmp.get_dividends(sym)
        if divs and isinstance(divs, list) and divs:
            extras["dividend_history"] = divs[:4]

        # DCF valuation
        dcf = fmp.get_dcf(sym)
        if dcf and dcf.get("dcf_value") is not None:
            extras["dcf_value"] = round(float(dcf["dcf_value"]), 2)

        return extras
    except Exception:
        return None


@router.get("/{ticker}/stream")
async def stream_stock_score(
    ticker: str,
    market: Literal["US", "IN", "GLOBAL"] = Query("US"),
    engine: Any = Depends(get_signal_engine),
):
    """SSE endpoint: emits score updates every 60 seconds for the given ticker.
    Uses cache first, falls back to live compute only on cache miss.
    """
    async def event_generator():
        last_score = None
        while True:
            try:
                # Offload sync get_stock_score to thread pool so event loop stays free
                score_obj = await asyncio.to_thread(get_stock_score, ticker, market, engine)
                payload = score_obj.model_dump_json()
                if last_score != payload:
                    yield f"event: score\ndata: {payload}\n\n"
                    last_score = payload
                else:
                    yield f"event: heartbeat\ndata: {{}}\n\n"
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
            await asyncio.sleep(60)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{ticker}/options")
async def get_options_snapshot(ticker: str, market: str = Query("US")):
    """Analyst consensus + share statistics from OpenBB.
    Returns consensus recommendation, target prices, and ownership data.
    Returns empty dict if OpenBB disabled.
    """
    try:
        from nq_data.openbb import get_openbb_client, _obb_symbol
        obb = get_openbb_client()
        if not obb.enabled:
            return {"enabled": False, "ticker": ticker, "data": {}}

        obb_sym = _obb_symbol(ticker, market)

        result = {"enabled": True, "ticker": ticker, "data": {}}

        # Analyst consensus (recommendation, target prices, analyst count)
        consensus = await asyncio.to_thread(obb.get_consensus, obb_sym)
        if consensus and isinstance(consensus, dict):
            result["data"]["consensus"] = consensus

        # Share statistics (ownership, short interest)
        ownership = await asyncio.to_thread(obb.get_ownership, obb_sym)
        if ownership and isinstance(ownership, dict):
            result["data"]["ownership"] = ownership

        return result
    except Exception as exc:
        log.warning("Options/consensus snapshot failed for %s: %s", ticker, exc)
        return {"enabled": True, "ticker": ticker, "data": {}, "error": str(exc)}


@router.get("/macro/yield-curve")
async def get_yield_curve():
    """US Treasury yield curve data from OpenBB. Returns empty dict if OpenBB disabled."""
    try:
        from nq_data.openbb import get_openbb_client
        obb = get_openbb_client()
        if not obb.enabled:
            return {"enabled": False, "data": {}}

        yc = await asyncio.to_thread(obb.get_yield_curve)
        if yc and isinstance(yc, list):
            # Convert list of {maturity, rate} to keyed dict for easier consumption
            yc_map = {p["maturity"]: round(float(p["rate"]) * 100, 2) for p in yc if isinstance(p, dict) and "maturity" in p and "rate" in p}
            return {"enabled": True, "data": yc_map}
        return {"enabled": True, "data": {}}
    except Exception as exc:
        log.warning("Yield curve fetch failed: %s", exc)
        return {"enabled": True, "data": {}, "error": str(exc)}


@router.get("/{ticker}/quantfactor")
async def get_quantfactor_detail(ticker: str, market: str = "US"):
    """Full QuantFactor enrichment row including IRS scores for a single ticker.
    Reads from quantfactor_universe via in-memory cache (O(1) lookup)."""
    t_up = _normalize_ticker(ticker, market)

    # Use the in-memory cache for sub-50ms response
    row = get_quantfactor_scores(t_up, market)

    # Fallback: bare ticker for Indian stocks
    if not row:
        bare = t_up.replace(".NS", "").replace(".BO", "")
        row = get_quantfactor_scores(bare, market)

    if not row:
        raise HTTPException(status_code=404, detail=f"QuantFactor data not found for {ticker}")

    # Add IRS interpretation
    irs_pct = row.get("irs_pct")
    g_score = row.get("g_score")
    risk_eff = row.get("risk_eff_score")
    interpretation = "N/A"
    if irs_pct is not None:
        if irs_pct > 65:
            interpretation = "STRONG BUY"
        elif irs_pct >= 45:
            interpretation = "MODERATE"
        elif irs_pct >= 30:
            interpretation = "WEAK"
        else:
            interpretation = "VERY WEAK"
    if g_score is not None and g_score < -0.5:
        interpretation = "NEUTRAL ZONE"
    if g_score is not None and g_score < -4:
        interpretation = "SELL (G Score)"
    if risk_eff is not None and risk_eff < -3.5:
        interpretation = "SELL (Risk)"

    row["irs_interpretation"] = interpretation
    row["sebi_disclaimer"] = (
        "NeuralQuant is a research tool, not a SEBI-registered investment advisor. "
        "Please consult a qualified financial advisor before investing."
    )
    return row

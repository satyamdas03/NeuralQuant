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

# In-memory TTL cache for stock meta — serves stale data when Yahoo rate-limits
_META_CACHE: dict[str, tuple[dict, float]] = {}
_META_CACHE_TTL = 3600  # 1 hour — balance between API calls and freshness

router = APIRouter()

_PERIOD_MAP = {
    "1d":  ("1d",  "5m"),
    "5d":  ("5d",  "30m"),
    "1mo": ("1mo", "1d"),
    "3mo": ("3mo", "1d"),
    "1y":  ("1y",  "1d"),
    "5y":  ("5y",  "1wk"),
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
                log.info("score_cache: serving stale (>%5min) for %s/%s", ticker_upper, market)
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
    # On Render, yfinance is rate-limited — skip live compute and return 504 fast.
    import os
    if os.environ.get("RENDER"):
        log.warning("score_cache empty for %s/%s on Render, skipping rate-limited live compute", ticker_upper, market)
        raise HTTPException(
            status_code=503,
            detail=f"Score data for {ticker_upper} is being refreshed. Please retry in 1-2 minutes.",
        )
    try:
        snapshot = await asyncio.wait_for(
            asyncio.to_thread(build_real_snapshot, [ticker_upper], market),
            timeout=25.0,
        )
    except asyncio.TimeoutError:
        log.warning("build_real_snapshot timed out for %s", ticker_upper)
        raise HTTPException(
            status_code=504,
            detail=f"Score cache miss for {ticker_upper}; upstream data source is rate-limited. Please retry in ~60s.",
        )
    except Exception as e:
        log.error("build_real_snapshot failed for %s: %s", ticker_upper, e)
        raise HTTPException(status_code=504, detail=f"Data fetch failed for {ticker_upper}. Try again in 30s.")

    if snapshot is None or snapshot.fundamentals.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")

    result_df = await asyncio.to_thread(engine.compute, snapshot)

    # BUG-001 fix: reject tickers that yfinance couldn't find
    fund_data = _fund_cache.get(f"{ticker_upper}:{market}", {})
    if not fund_data.get("_is_real") and ticker_upper not in UNIVERSE_BY_MARKET.get(market, UNIVERSE_BY_MARKET["US"]):
        raise HTTPException(
            status_code=404,
            detail=f"Ticker '{ticker_upper}' not found in {market} market. "
                   "Check the ticker symbol and market parameter."
        )

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
            logger.debug("Non-critical enrichment failed: %s", e)
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

    # Primary path: yfinance (offloaded to thread pool)
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

    # Fallback: hit Yahoo chart API directly.
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
    Also treats pre-enrichment cached data (missing or None enrichment fields) as incomplete."""
    if any(_is_nullish(meta, k) for k in _NULL_FIELDS):
        return True
    # Enrichment fields must be present AND have at least one non-None value
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


@router.get("/{ticker}/meta")
async def get_stock_meta(ticker: str, market: str = Query("US")):
    t_up = _normalize_ticker(ticker, market)
    cache_key = f"{t_up}:{market}"

    # Serve from in-memory cache if fresh AND complete
    cached = _META_CACHE.get(cache_key)
    if cached and (time.monotonic() - cached[1]) < _META_CACHE_TTL:
        if not _has_null_fields(cached[0]):
            return cached[0]
        # Cached data has nulls — fall through to refetch

    # Try Supabase persistent cache — but only serve if fresh AND complete
    from nq_api.cache.score_cache import _supabase_rest
    supa_row = None
    supa = _supabase_rest(
        "stock_meta",
        method="GET",
        query={
            "select": "data,fetched_at",
            "ticker": f"eq.{t_up}",
            "market": f"eq.{market}",
            "order": "fetched_at.desc",
            "limit": "1",
        },
    )
    if isinstance(supa, list) and supa:
        import json as _json
        try:
            meta = _json.loads(supa[0]["data"]) if isinstance(supa[0]["data"], str) else supa[0]["data"]
            fetched_at = supa[0].get("fetched_at", "")
            # Only serve from cache if fresh (< 6h) AND has no null critical fields
            age_hours = 999
            if fetched_at:
                try:
                    from datetime import datetime as _dt, timezone as _tz
                    fa = _dt.fromisoformat(fetched_at.replace("Z", "+00:00"))
                    age_hours = (_dt.now(_tz.utc) - fa).total_seconds() / 3600
                except Exception:
                    pass
            if age_hours < 6 and not _has_null_fields(meta):
                _META_CACHE[cache_key] = (meta, time.monotonic())
                return meta
            supa_row = meta  # keep for merging later
        except Exception:
            log.warning("meta Supabase cache parse failed for %s", t_up)

    # Primary: FMP (Financial Modeling Prep) — reliable, no Yahoo 401
    fmp_meta = await asyncio.to_thread(_fetch_stock_meta_fmp, t_up, market)
    if isinstance(fmp_meta, dict) and not _has_null_fields(fmp_meta):
        _META_CACHE[cache_key] = (fmp_meta, time.monotonic())
        _persist_meta(t_up, market, fmp_meta)
        return fmp_meta
    if isinstance(fmp_meta, dict):
        # FMP partial — merge with Supabase/score_cache to fill gaps
        merged = _merge_meta(fmp_meta, supa_row) if supa_row else fmp_meta
        if _has_null_fields(merged):
            sc = _read_score_cache(t_up, market)
            if sc:
                merged = _merge_meta(merged, sc)
        # Always try yfinance for partial FMP — it may have fresh P/E, price, etc.
        # that Supabase cache doesn't (stale values). _merge_meta only fills nulls,
        # so yfinance won't overwrite FMP values (FMP is authoritative for name/beta/sector).
        yf_result = await asyncio.to_thread(_fetch_stock_meta, t_up, market)
        if isinstance(yf_result, dict):
            merged = _merge_meta(merged, yf_result)
            # For P/E and current_price, prefer yfinance fresh data over stale cache
            if yf_result.get("pe_ttm") and merged.get("pe_ttm") != yf_result["pe_ttm"]:
                merged["pe_ttm"] = yf_result["pe_ttm"]
            if yf_result.get("current_price") and merged.get("current_price") != yf_result["current_price"]:
                merged["current_price"] = yf_result["current_price"]
        _META_CACHE[cache_key] = (merged, time.monotonic())
        _persist_meta(t_up, market, merged)
        return merged

    # Secondary: yfinance
    result = await asyncio.to_thread(_fetch_stock_meta, t_up, market)
    if isinstance(result, dict):
        # Merge with Supabase cache or score_cache to fill any nulls
        if _has_null_fields(result):
            merged = _merge_meta(result, supa_row) if supa_row else result
            if _has_null_fields(merged):
                sc = _read_score_cache(t_up, market)
                if sc:
                    merged = _merge_meta(merged, sc)
            result = merged
        _META_CACHE[cache_key] = (result, time.monotonic())
        _persist_meta(t_up, market, result)
        return result

    # Fallback: Yahoo quoteSummary v10 (with 1 retry)
    log.warning("meta yfinance failed for %s (%s) — trying Yahoo fallback: %s",
                t_up, market, result)
    fallback = await asyncio.to_thread(_fetch_stock_meta_yahoo_direct, t_up, market)
    if isinstance(fallback, dict):
        if _has_null_fields(fallback):
            merged = _merge_meta(fallback, supa_row) if supa_row else fallback
            if _has_null_fields(merged):
                sc = _read_score_cache(t_up, market)
                if sc:
                    merged = _merge_meta(merged, sc)
            fallback = merged
        _META_CACHE[cache_key] = (fallback, time.monotonic())
        _persist_meta(t_up, market, fallback)
        return fallback

    # Fallback: merge Supabase cache + score_cache
    sc = _read_score_cache(t_up, market)
    if supa_row or sc:
        base = supa_row or _build_from_score_cache(t_up, market, sc) or _empty_meta(t_up)
        merged = base
        if sc:
            merged = _merge_meta(merged, sc)
        _META_CACHE[cache_key] = (merged, time.monotonic())
        log.info("meta: serving merged cache for %s", t_up)
        return merged

    # Both failed — serve stale cache if available, else minimal response
    if cached:
        log.warning("meta both paths failed for %s — serving stale cache", t_up)
        return cached[0]

    log.error("meta all sources failed for %s and no cache", t_up)
    return _empty_meta(t_up)


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
    from nq_api.cache.score_cache import _supabase_rest
    from datetime import datetime, timezone

    try:
        row = {
            "ticker": ticker,
            "market": market,
            "data": _json.dumps(data),
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
        logger.debug("Non-critical enrichment failed: %s", e)
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
        try:
            # Analyst price target
            tgt = fmp.get_price_target(sym)
            if tgt and tgt.get("target_avg") is not None:
                meta["analyst_target"] = round(float(tgt["target_avg"]), 2)

            # Analyst consensus grade
            grades = fmp.get_analyst_grades(sym)
            if grades and grades.get("consensus"):
                meta["analyst_recommendation"] = grades["consensus"]

            # Upcoming earnings date
            from datetime import date as _date, timedelta as _td
            today = _date.today()
            earnings = fmp.get_earnings_calendar(today.isoformat(), (today + _td(days=30)).isoformat())
            if earnings and isinstance(earnings, list):
                ticker_earnings = [
                    e for e in earnings
                    if e.get("ticker", "").upper() == ticker.upper()
                    or e.get("ticker", "").upper() == sym.upper()
                ]
                if ticker_earnings and ticker_earnings[0].get("date"):
                    meta["earnings_date"] = ticker_earnings[0]["date"]

            # Dividend history (latest 4)
            divs = fmp.get_dividends(sym)
            if divs and isinstance(divs, list) and divs:
                meta["dividend_history"] = divs[:4]

            # Analyst estimates (revenue + EPS consensus)
            estimates = fmp.get_analyst_estimates(sym)
            if estimates:
                if estimates.get("revenue_estimate") is not None:
                    meta["analyst_revenue_est"] = float(estimates["revenue_estimate"])
                if estimates.get("eps_estimate") is not None:
                    meta["analyst_eps_est"] = float(estimates["eps_estimate"])

            # Financial scores (Altman Z, Piotroski)
            scores = fmp.get_financial_scores(sym)
            if scores:
                if scores.get("altman_z_score") is not None:
                    meta["altman_z_score"] = round(float(scores["altman_z_score"]), 2)
                if scores.get("piotroski_score") is not None:
                    meta["piotroski_score"] = int(scores["piotroski_score"])

            # Insider trading summary
            insider = fmp.get_insider_trading(sym)
            if insider and isinstance(insider, list):
                buys = sum(1 for t in insider if "Buy" in str(t.get("transaction_type", "")))
                sells = sum(1 for t in insider if "Sell" in str(t.get("transaction_type", "")))
                meta["insider_buys"] = buys
                meta["insider_sells"] = sells

            # DCF valuation
            dcf = fmp.get_dcf(sym)
            if dcf and dcf.get("dcf_value") is not None:
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
                obb_sym = _yf_symbol(ticker, market) if market == "IN" else ticker

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
            "current_price":           info.get("currentPrice") or info.get("regularMarketPrice"),
        }
    except Exception as exc:
        return exc


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

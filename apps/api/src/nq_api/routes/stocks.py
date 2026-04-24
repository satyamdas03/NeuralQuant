import logging
from typing import Literal
import asyncio
import json

import httpx
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

log = logging.getLogger(__name__)

from nq_api.deps import get_signal_engine
from nq_api.schemas import AIScore
from nq_api.score_builder import row_to_ai_score, rank_scores_in_universe
from nq_api.universe import UNIVERSE_BY_MARKET
from nq_api.data_builder import build_real_snapshot, _fund_cache, fetch_real_macro
from nq_api.cache import score_cache
from nq_signals.engine import SignalEngine

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
    engine: SignalEngine = Depends(get_signal_engine),
) -> AIScore:
    ticker_upper = ticker.upper()

    # --- Fast path: read from Supabase score_cache (sub-100ms) ---
    try:
        cached = await asyncio.to_thread(score_cache.read_one, ticker_upper, market, max_age_seconds=172800)
    except Exception as e:
        log.warning("score_cache.read_one failed: %s", e)
        cached = None
    if cached:
        # Build AIScore from cache row — use regime_id from cache row itself
        df = pd.DataFrame([cached])
        if "regime_id" not in df.columns or pd.isna(df["regime_id"].iloc[0]):
            df["regime_id"] = 1
        return row_to_ai_score(df.iloc[0], market, score_1_10_override=_score_1_10_from_cache(cached))

    # --- Slow path: live compute (fallback for cache miss) ---
    # Compute ONLY this ticker's data, not the whole universe.
    # This is much faster than building the entire universe snapshot.
    try:
        snapshot = await asyncio.to_thread(build_real_snapshot, [ticker_upper], market)
    except Exception as e:
        log.error("build_real_snapshot failed for %s: %s", ticker_upper, e)
        raise HTTPException(status_code=504, detail=f"Data fetch timed out for {ticker_upper}. Try again in 30s.")

    if snapshot is None or snapshot.empty:
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

    ranked_scores = rank_scores_in_universe(result_df)
    ticker_idx = matching.index[0]
    score_override = int(ranked_scores.iloc[ticker_idx]) if ticker_idx < len(ranked_scores) else None

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
    yrange, yinterval = _YAHOO_RANGE_MAP.get(period, ("1mo", "1d"))
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
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
        except Exception:
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
            hist = yf.Ticker(sym).history(period=yf_period, interval=interval, auto_adjust=True)
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


@router.get("/{ticker}/meta")
async def get_stock_meta(ticker: str, market: str = Query("US")):
    result = await asyncio.to_thread(_fetch_stock_meta, ticker.upper(), market)
    if isinstance(result, dict):
        return result
    raise HTTPException(500, str(result))


def _fetch_stock_meta(ticker: str, market: str) -> dict | Exception:
    """Blocking yfinance calls — run in thread pool."""
    sym = _yf_sym(ticker, market)
    try:
        t = yf.Ticker(sym)
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
            "market_cap_fmt":          _fmt_mcap(float(mc), market) if mc else None,
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
    engine: SignalEngine = Depends(get_signal_engine),
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

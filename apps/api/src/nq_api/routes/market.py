"""GET /market — live market data via FMP (primary) with yfinance fallback."""
import asyncio
import time
import logging
from fastapi import APIRouter
import yfinance as yf
import pandas as pd

from nq_api.data_builder import _get_yf_session, _fetch_yf_info_cached, _IS_RENDER
from nq_api.universe import UNIVERSE_BY_MARKET

logger = logging.getLogger(__name__)

router = APIRouter()

_INDICES = {
    "^GSPC": "S&P 500",
    "^IXIC": "NASDAQ",
    "^DJI": "Dow Jones",
    "^VIX": "VIX",
}

_INDICES_IN = {
    "^NSEI": "Nifty 50",
    "^BSESN": "Sensex",
    "^INDIAVIX": "India VIX",
    "^NSEBANK": "Bank Nifty",
}

_FUTURES = {
    "ES=F": "S&P Futures",
    "NQ=F": "NASDAQ Futures",
    "YM=F": "Dow Futures",
}

_FUTURES_IN = {
    "SGXCN1.NV": "GIFT Nifty Futures",
}

_SECTORS = {
    "XLK": "Technology",
    "XLE": "Energy",
    "XLF": "Financial Services",
    "XLV": "Healthcare",
    "XLY": "Consumer Cyclical",
    "XLP": "Consumer Defensive",
    "XLI": "Industrials",
    "XLB": "Basic Materials",
    "XLRE": "Real Estate",
    "XLU": "Utilities",
    "XLC": "Communication Services",
}

# ─── In-memory caches ──────────────────────────────────────────────────────────

_overview_cache: dict = {}
_overview_ts: float = 0.0
OVERVIEW_TTL = 300  # 5 minutes

_sector_cache: dict = {}
_sector_ts: float = 0.0
SECTOR_TTL = 300  # 5 minutes

_movers_cache: dict = {}
_movers_ts: float = 0.0
MOVERS_TTL = 1800  # 30 minutes (stale-while-revalidate)

_news_cache: dict = {}
_news_ts: float = 0.0
NEWS_TTL = 600  # 10 minutes


def _pct_change_from_info(sym: str) -> dict | None:
    """Get price/change from cached yfinance .info (1h TTL, works on Render)."""
    info = _fetch_yf_info_cached(sym)
    if not info.get("_cached_ok"):
        return None
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    prev = info.get("previousClose") or info.get("regularMarketPreviousClose")
    if price and prev and prev > 0:
        change_abs = price - prev
        change_pct = (change_abs / prev * 100)
        return {
            "price": round(price, 2),
            "change_pct": round(change_pct, 2),
            "change_abs": round(change_abs, 2),
        }
    return None


def _batch_pct_change(symbols: list[str]) -> dict[str, dict]:
    """Fetch price and % change for multiple symbols using yf.download (batch).
    This works on Render where individual yf.Ticker().history() calls fail."""
    result = {}
    try:
        raw = yf.download(
            symbols, period="5d", progress=False,
            auto_adjust=True, threads=False,
            session=_get_yf_session(),
        )
        if raw.empty:
            return result
        close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
        for sym in symbols:
            try:
                if isinstance(close, pd.DataFrame) and sym in close.columns:
                    closes = close[sym].dropna()
                elif isinstance(close, pd.Series):
                    closes = close.dropna()
                else:
                    continue
                if len(closes) < 2:
                    continue
                price = float(closes.iloc[-1])
                prev = float(closes.iloc[-2])
                if prev <= 0:
                    continue
                chg_abs = round(price - prev, 2)
                chg_pct = round((chg_abs / prev * 100), 2)
                result[sym] = {"price": round(price, 2), "change_pct": chg_pct, "change_abs": chg_abs}
            except Exception:
                continue
    except Exception as exc:
        logger.warning("batch_pct_change failed: %s", exc)
    return result


@router.get("/overview")
async def market_overview(market: str = "US"):
    global _overview_cache, _overview_ts
    now = time.time()

    # Return cached if fresh
    cached = _overview_cache.get(market.upper())
    if cached and now - _overview_ts < OVERVIEW_TTL:
        return cached

    data = await asyncio.to_thread(_market_overview_sync, market.upper())
    if _overview_cache is None:
        _overview_cache = {}
    _overview_cache[market.upper()] = data
    _overview_ts = now
    return data


def _market_overview_sync(market: str = "US"):
    idx_map = _INDICES_IN if market == "IN" else _INDICES
    fut_map = _FUTURES_IN if market == "IN" else _FUTURES

    # Try FMP first for batch quotes
    fmp_ok = False
    indices = []
    futures = []
    try:
        from nq_data.fmp import get_fmp_client
        fmp = get_fmp_client()
        if fmp._enabled:
            all_syms = list(idx_map.keys()) + list(fut_map.keys())
            batch = fmp.get_batch_quotes(all_syms)
            if batch and len(batch) > 0:
                for sym, name in idx_map.items():
                    q = batch.get(sym)
                    if q and q.get("price") is not None:
                        indices.append({
                            "symbol": sym, "name": name,
                            "price": round(float(q["price"]), 2),
                            "change_pct": round(float(q.get("change_pct") or 0), 2),
                            "change_abs": round(float(q.get("change") or 0), 2),
                        })
                    else:
                        d = _pct_change_from_info(sym) or {"price": 0.0, "change_pct": 0.0, "change_abs": 0.0}
                        indices.append({"symbol": sym, "name": name, **d})
                for sym, name in fut_map.items():
                    q = batch.get(sym)
                    if q and q.get("price") is not None:
                        futures.append({
                            "symbol": sym, "name": name,
                            "price": round(float(q["price"]), 2),
                            "change_pct": round(float(q.get("change_pct") or 0), 2),
                            "change_abs": round(float(q.get("change") or 0), 2),
                        })
                    else:
                        d = _pct_change_from_info(sym) or {"price": 0.0, "change_pct": 0.0, "change_abs": 0.0}
                        futures.append({"symbol": sym, "name": name, **d})
                fmp_ok = True
    except Exception as exc:
        logger.debug("FMP market overview failed: %s — falling back to yfinance", exc)

    if not fmp_ok:
        # Fallback: yfinance batch download
        all_syms = list(idx_map.keys()) + list(fut_map.keys())
        batch_data = _batch_pct_change(all_syms)
        for sym, name in idx_map.items():
            d = batch_data.get(sym) or _pct_change_from_info(sym) or {"price": 0.0, "change_pct": 0.0, "change_abs": 0.0}
            indices.append({"symbol": sym, "name": name, **d})
        for sym, name in fut_map.items():
            d = batch_data.get(sym) or _pct_change_from_info(sym) or {"price": 0.0, "change_pct": 0.0, "change_abs": 0.0}
            futures.append({"symbol": sym, "name": name, **d})

    return {"indices": indices, "futures": futures}


@router.get("/news")
async def market_news(n: int = 8):
    global _news_cache, _news_ts
    now = time.time()
    if _news_cache and now - _news_ts < NEWS_TTL:
        return {**_news_cache, "n": min(n, len(_news_cache.get("news", [])))}
    return await asyncio.to_thread(_market_news_sync, n)


def _market_news_sync(n: int = 8):
    global _news_cache, _news_ts
    try:
        items = yf.Ticker("^GSPC", session=_get_yf_session()).news or []
        result = []
        for item in items[:n]:
            content = item.get("content") or {}
            title = content.get("title") or item.get("title", "")
            publisher = (
                (content.get("provider") or {}).get("displayName")
                or item.get("publisher", "")
            )
            url = (
                (content.get("canonicalUrl") or {}).get("url")
                or item.get("link", "")
            )
            pub_date = content.get("pubDate") or str(item.get("providerPublishTime", ""))
            if title:
                result.append(
                    {"title": title, "publisher": publisher, "url": url, "time": pub_date}
                )
        _news_cache = {"news": result}
        _news_ts = time.time()
        return {"news": result}
    except Exception as exc:
        logger.debug("Market news fetch failed: %s", exc)
        return {"news": [], "error": str(exc)}


@router.get("/sectors")
async def market_sectors():
    global _sector_cache, _sector_ts
    if _sector_cache and time.time() - _sector_ts < SECTOR_TTL:
        return _sector_cache
    # Always compute fresh (5 min cache, no stale-while-revalidate to avoid 0.0)
    return await asyncio.to_thread(_market_sectors_sync)


def _market_sectors_sync():
    global _sector_cache, _sector_ts
    # Try FMP sector-performance-snapshot first
    fmp_ok = False
    sectors = []
    try:
        from nq_data.fmp import get_fmp_client
        fmp = get_fmp_client()
        if fmp._enabled:
            from datetime import date as _date, timedelta as _td
            # Try today first, then yesterday (market data may not be ready)
            for d in [_date.today(), _date.today() - _td(days=1)]:
                fmp_sectors = fmp.get_sector_performance(d.isoformat())
                if fmp_sectors and len(fmp_sectors) > 0:
                    # Map FMP sector names to our ETF symbols
                    name_to_sym = {v: k for k, v in _SECTORS.items()}
                    for s in fmp_sectors:
                        name = s.get("sector", "")
                        chg = s.get("change_pct")
                        # FMP returns averageChange as decimal percentage (e.g. -0.1129 = -0.11%)
                        if chg is None and s.get("averageChange") is not None:
                            chg = round(float(s["averageChange"]), 2)
                        sym = name_to_sym.get(name, "")
                        if sym:
                            sectors.append({"symbol": sym, "name": name, "change_pct": chg or 0.0})
                    # Fill any missing sectors with yfinance fallback
                    found_syms = {s["symbol"] for s in sectors}
                    for sym, name in _SECTORS.items():
                        if sym not in found_syms:
                            d = _pct_change_from_info(sym)
                            sectors.append({"symbol": sym, "name": name, "change_pct": d["change_pct"] if d else 0.0})
                    fmp_ok = True
                    break
    except Exception as exc:
        logger.debug("FMP sector performance failed: %s — falling back to yfinance", exc)

    if not fmp_ok:
        # Fallback: yfinance batch download
        syms = list(_SECTORS.keys())
        batch_data = _batch_pct_change(syms)
        for sym, name in _SECTORS.items():
            d = batch_data.get(sym) or _pct_change_from_info(sym)
            change_pct = d["change_pct"] if d else 0.0
            sectors.append({"symbol": sym, "name": name, "change_pct": change_pct})

    result = {"sectors": sectors}
    _sector_cache = result
    _sector_ts = time.time()
    return result


_MOVERS_UNIVERSE = [
    "AAPL","MSFT","GOOGL","AMZN","NVDA","META","TSLA","BRK-B","JPM","V",
    "MA","UNH","XOM","JNJ","HD","COST","ABBV","LLY","CVX","BAC",
    "NFLX","ORCL","ADBE","CRM","AMD","AVGO","WMT","MCD","PFE","ISRG",
]


@router.get("/movers")
async def market_movers():
    global _movers_cache, _movers_ts
    if _movers_cache and time.time() - _movers_ts < MOVERS_TTL:
        return _movers_cache
    if _movers_cache:
        asyncio.create_task(_refresh_movers())
        return {**_movers_cache, "stale": True}
    return await asyncio.to_thread(_market_movers_sync)


async def _refresh_movers():
    await asyncio.to_thread(_market_movers_sync)


def _market_movers_sync():
    global _movers_cache, _movers_ts
    # Try FMP market movers first
    try:
        from nq_data.fmp import get_fmp_client
        fmp = get_fmp_client()
        if fmp._enabled:
            gainers = fmp.get_market_movers("gainers") or []
            losers = fmp.get_market_movers("losers") or []
            actives = fmp.get_market_movers("active") or []
            if gainers or losers or actives:
                def _to_mover(m):
                    price = m.get("price")
                    if price is not None and float(price) < 5:
                        return None
                    ticker = m.get("ticker", "")
                    return {
                        "ticker": ticker,
                        "name": m.get("name", ""),
                        "price": m.get("price"),
                        "change_pct": m.get("change_pct"),
                        "change_abs": m.get("change"),
                        "volume": m.get("volume"),
                    }
                result = {
                    "gainers": [x for x in (_to_mover(m) for m in gainers[:50]) if x][:5],
                    "losers": [x for x in (_to_mover(m) for m in losers[:50]) if x][:5],
                    "active": [x for x in (_to_mover(m) for m in actives[:50]) if x][:5],
                }
                if any(result.values()):
                    _movers_cache = result
                    _movers_ts = time.time()
                    return result
                logger.warning("FMP movers: all results filtered out (g=%d l=%d a=%d)", len(gainers), len(losers), len(actives))
            else:
                logger.warning("FMP movers returned empty for all categories")
    except Exception as exc:
        logger.warning("FMP market movers failed: %s — falling back to yfinance", exc)

    # Fallback: individual yfinance .info calls (more reliable than batch yf.download on Render)
    rows = []
    for sym in _MOVERS_UNIVERSE:
        try:
            info = _fetch_yf_info_cached(sym)
            if not info.get("_cached_ok"):
                # Bypass failure cache with a direct fetch
                try:
                    t = yf.Ticker(sym, session=_get_yf_session())
                    info = t.info or {}
                except Exception:
                    continue
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            prev = info.get("previousClose") or info.get("regularMarketPreviousClose")
            vol = info.get("volume") or info.get("regularMarketVolume")
            if price and prev and prev > 0:
                chg_abs = round(price - prev, 2)
                chg_pct = round((chg_abs / prev * 100), 2)
                rows.append({
                    "ticker": sym,
                    "name": info.get("longName") or info.get("shortName") or sym,
                    "price": round(price, 2),
                    "change_pct": chg_pct,
                    "change_abs": chg_abs,
                    "volume": vol,
                })
        except Exception:
            pass

    # Filter out penny stocks (<$5) and stocks without names
    rows = [r for r in rows if r["price"] >= 5 and r.get("name")]

    if rows:
        rows_sorted = sorted(rows, key=lambda x: x["change_pct"], reverse=True)
        result = {
            "gainers": rows_sorted[:5],
            "losers": list(reversed(rows_sorted[-5:])),
            "active": sorted(rows, key=lambda x: x["volume"] or 0, reverse=True)[:5],
        }
        _movers_cache = result
        _movers_ts = time.time()
        return result
    logger.warning("yfinance movers fallback returned 0 valid rows")

    # Last resort: return stale cache if available, otherwise error
    if _movers_cache:
        logger.warning("Movers: all sources failed, returning stale cache (age=%ds)", int(time.time() - _movers_ts))
        return {**_movers_cache, "stale": True}
    return {"gainers": [], "losers": [], "active": [], "error": "All data sources failed"}


@router.get("/data-quality")
async def data_quality():
    """Shows live data quality: how many tickers are real vs synthetic, full macro snapshot."""
    from nq_api.data_builder import _fund_cache, _fund_ts, _macro_cache, _macro_ts, FUND_TTL
    import os
    now = time.time()
    real = sum(
        1 for k, v in _fund_cache.items()
        if v.get("_is_real") and now - _fund_ts.get(k, 0) < FUND_TTL
    )
    synthetic = sum(
        1 for k, v in _fund_cache.items()
        if not v.get("_is_real") and now - _fund_ts.get(k, 0) < FUND_TTL
    )
    macro_fresh = _macro_cache is not None and now - _macro_ts < 3600
    m = _macro_cache
    return {
        "tickers_with_real_data": real,
        "tickers_with_synthetic_fallback": synthetic,
        "total_cached": real + synthetic,
        "macro_is_real": macro_fresh,
        "fred_sourced": getattr(m, "fred_sourced", False) if macro_fresh else False,
        "fred_key_configured": bool(os.environ.get("FRED_API_KEY", "").strip()),
        "macro": {
            "vix": getattr(m, "vix", None) if macro_fresh else None,
            "spx_vs_200ma_pct": round(getattr(m, "spx_vs_200ma", 0) * 100, 2) if macro_fresh else None,
            "spx_return_1m_pct": round(getattr(m, "spx_return_1m", 0) * 100, 2) if macro_fresh else None,
            "hy_spread_oas": getattr(m, "hy_spread_oas", None) if macro_fresh else None,
            "ism_pmi": getattr(m, "ism_pmi", None) if macro_fresh else None,
            "yield_10y": getattr(m, "yield_10y", None) if macro_fresh else None,
            "yield_2y": getattr(m, "yield_2y", None) if macro_fresh else None,
            "yield_spread_2y10y": getattr(m, "yield_spread_2y10y", None) if macro_fresh else None,
            "cpi_yoy": getattr(m, "cpi_yoy", None) if macro_fresh else None,
            "fed_funds_rate": getattr(m, "fed_funds_rate", None) if macro_fresh else None,
        } if macro_fresh else None,
    }
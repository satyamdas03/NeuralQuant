"""GET /market — live market data via yfinance."""
import asyncio
import time
from fastapi import APIRouter
import yfinance as yf
import pandas as pd
import logging
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


def _pct_change(sym: str) -> dict:
    try:
        t = yf.Ticker(sym)
        hist = t.history(period="2d", auto_adjust=True)
        if len(hist) >= 2:
            price = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
        elif len(hist) == 1:
            price = float(hist["Close"].iloc[-1])
            prev = price
        else:
            return {"price": 0.0, "change_pct": 0.0, "change_abs": 0.0}
        change_abs = price - prev
        change_pct = (change_abs / prev * 100) if prev else 0.0
        return {
            "price": round(price, 2),
            "change_pct": round(change_pct, 2),
            "change_abs": round(change_abs, 2),
        }
    except Exception as e:
        logger.debug("Non-critical enrichment failed: %s", e)
        return {"price": 0.0, "change_pct": 0.0, "change_abs": 0.0}


@router.get("/overview")
async def market_overview(market: str = "US"):
    data = await asyncio.to_thread(_market_overview_sync, market.upper())
    return data


def _market_overview_sync(market: str = "US"):
    idx_map = _INDICES_IN if market == "IN" else _INDICES
    fut_map = _FUTURES_IN if market == "IN" else _FUTURES
    indices = []
    for sym, name in idx_map.items():
        d = _pct_change(sym)
        indices.append({"symbol": sym, "name": name, **d})
    futures = []
    for sym, name in fut_map.items():
        d = _pct_change(sym)
        futures.append({"symbol": sym, "name": name, **d})
    return {"indices": indices, "futures": futures}


@router.get("/news")
async def market_news(n: int = 8):
    return await asyncio.to_thread(_market_news_sync, n)


def _market_news_sync(n: int = 8):
    try:
        items = yf.Ticker("^GSPC").news or []
        result = []
        for item in items[:n]:
            # yfinance v0.2.x uses nested "content" dict; fallback to flat dict
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
        return {"news": result}
    except Exception as exc:
        return {"news": [], "error": str(exc)}


@router.get("/sectors")
async def market_sectors():
    return await asyncio.to_thread(_market_sectors_sync)


def _market_sectors_sync():
    sectors = []
    for sym, name in _SECTORS.items():
        d = _pct_change(sym)
        sectors.append({"symbol": sym, "name": name, "change_pct": d["change_pct"]})
    return {"sectors": sectors}


_MOVERS_UNIVERSE = [
    "AAPL","MSFT","GOOGL","AMZN","NVDA","META","TSLA","BRK-B","JPM","V",
    "MA","UNH","XOM","JNJ","HD","COST","ABBV","LLY","CVX","BAC",
    "NFLX","ORCL","ADBE","CRM","AMD","AVGO","WMT","MCD","PFE","ISRG",
]

_movers_cache: dict = {}
_movers_ts: float = 0.0
MOVERS_TTL = 600  # 10 minutes


@router.get("/movers")
async def market_movers():
    global _movers_cache, _movers_ts
    if _movers_cache and time.time() - _movers_ts < MOVERS_TTL:
        return _movers_cache

    # Serve stale immediately + background refresh
    if _movers_cache:
        asyncio.create_task(_refresh_movers())
        return {**_movers_cache, "stale": True}

    # Cold start: block briefly to fill
    return await asyncio.to_thread(_market_movers_sync)


async def _refresh_movers():
    """Background refresh for market movers cache."""
    await asyncio.to_thread(_market_movers_sync)


def _market_movers_sync():
    global _movers_cache, _movers_ts
    try:
        raw = yf.download(
            _MOVERS_UNIVERSE, period="2d", progress=False,
            auto_adjust=True, threads=True,
        )
        # yf.download returns MultiIndex columns when >1 ticker
        close  = raw["Close"]  if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
        volume = raw["Volume"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Volume"]]

        rows = []
        for sym in _MOVERS_UNIVERSE:
            try:
                closes = close[sym].dropna()
                if len(closes) < 2:
                    continue
                price    = float(closes.iloc[-1])
                prev     = float(closes.iloc[-2])
                chg_abs  = round(price - prev, 2)
                chg_pct  = round((chg_abs / prev * 100) if prev else 0.0, 2)
                vol      = int(volume[sym].iloc[-1])
                rows.append({"ticker": sym, "price": round(price, 2),
                              "change_pct": chg_pct, "change_abs": chg_abs, "volume": vol})
            except Exception:
                pass

        rows_sorted = sorted(rows, key=lambda x: x["change_pct"], reverse=True)
        result = {
            "gainers": rows_sorted[:5],
            "losers":  list(reversed(rows_sorted[-5:])),
            "active":  sorted(rows, key=lambda x: x["volume"], reverse=True)[:5],
        }
        _movers_cache = result
        _movers_ts = time.time()
        return result
    except Exception as exc:
        return {"gainers": [], "losers": [], "active": [], "error": str(exc)}


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
            "vix":                getattr(m, "vix",                None) if macro_fresh else None,
            "spx_vs_200ma_pct":   round(getattr(m, "spx_vs_200ma", 0) * 100, 2) if macro_fresh else None,
            "spx_return_1m_pct":  round(getattr(m, "spx_return_1m", 0) * 100, 2) if macro_fresh else None,
            "hy_spread_oas":      getattr(m, "hy_spread_oas",      None) if macro_fresh else None,
            "ism_pmi":            getattr(m, "ism_pmi",            None) if macro_fresh else None,
            "yield_10y":          getattr(m, "yield_10y",          None) if macro_fresh else None,
            "yield_2y":           getattr(m, "yield_2y",           None) if macro_fresh else None,
            "yield_spread_2y10y": getattr(m, "yield_spread_2y10y", None) if macro_fresh else None,
            "cpi_yoy":            getattr(m, "cpi_yoy",            None) if macro_fresh else None,
            "fed_funds_rate":     getattr(m, "fed_funds_rate",     None) if macro_fresh else None,
        } if macro_fresh else None,
    }

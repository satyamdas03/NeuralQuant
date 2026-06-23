"""GET /market — live market data via FMP (primary) with yfinance fallback."""
import asyncio
import time
import logging
from fastapi import APIRouter, Query
import yfinance as yf
import pandas as pd

from nq_api.data_builder import _get_yf_session, _fetch_yf_info_cached, _IS_RENDER, _reset_yf_session
from nq_api.universe import UNIVERSE_BY_MARKET

logger = logging.getLogger(__name__)

router = APIRouter()

# Fast lookup set for universe membership check in movers
_US_UNIVERSE_SET: set[str] = set(UNIVERSE_BY_MARKET.get("US", []))
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
_overview_ts: dict[str, float] = {}
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


def _is_yf_crumb_error(exc: Exception) -> bool:
    """Detect yfinance 'Invalid Crumb' or 401 auth errors."""
    msg = str(exc).lower()
    return "crumb" in msg or "401" in msg or "unauthorized" in msg


def _batch_pct_change(symbols: list[str]) -> dict[str, dict]:
    """Fetch price and % change for multiple symbols using yf.download (batch).
    This works on Render where individual yf.Ticker().history() calls fail."""
    result = {}
    for attempt in range(2):
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
            break  # success
        except Exception as exc:
            if _is_yf_crumb_error(exc) and attempt == 0:
                logger.warning("batch_pct_change crumb error, resetting session and retrying")
                _reset_yf_session()
                continue
            logger.warning("batch_pct_change failed: %s", exc)
    return result


@router.get("/overview")
async def market_overview(market: str = "US"):
    global _overview_cache, _overview_ts
    now = time.time()
    mkt = market.upper()

    # Return cached if fresh
    cached = _overview_cache.get(mkt)
    if cached and now - _overview_ts.get(mkt, 0) < OVERVIEW_TTL:
        return cached

    try:
        data = await asyncio.wait_for(
            asyncio.to_thread(_market_overview_sync, mkt),
            timeout=20.0,
        )
    except asyncio.TimeoutError:
        logger.warning("market_overview: _market_overview_sync timed out for %s", mkt)
        data = {"indices": [], "futures": []}
    _overview_cache[mkt] = data
    _overview_ts[mkt] = now
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
        # Fallback: yfinance batch download (defensive — can hang on Render)
        try:
            all_syms = list(idx_map.keys()) + list(fut_map.keys())
            batch_data = _batch_pct_change(all_syms)
            for sym, name in idx_map.items():
                d = batch_data.get(sym) or _pct_change_from_info(sym) or {"price": 0.0, "change_pct": 0.0, "change_abs": 0.0}
                indices.append({"symbol": sym, "name": name, **d})
            for sym, name in fut_map.items():
                d = batch_data.get(sym) or _pct_change_from_info(sym) or {"price": 0.0, "change_pct": 0.0, "change_abs": 0.0}
                futures.append({"symbol": sym, "name": name, **d})
        except Exception:
            logger.exception("market_overview yfinance fallback failed for %s", market)

    # Hard guarantee: if indices/futures are still empty, fill with zero-dict stubs
    # so frontend never sees "unavailable".
    if not indices:
        for sym, name in idx_map.items():
            indices.append({"symbol": sym, "name": name, "price": 0.0, "change_pct": 0.0, "change_abs": 0.0})
    if not futures:
        for sym, name in fut_map.items():
            futures.append({"symbol": sym, "name": name, "price": 0.0, "change_pct": 0.0, "change_abs": 0.0})

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
    result = []
    source_used = None

    # ── Source 1: FMP market news (primary — works on Render) ──────────────
    try:
        from nq_data.fmp import get_fmp_client
        fmp = get_fmp_client()
        if fmp._enabled:
            fmp_news = fmp.get_market_news(limit=n + 2)  # fetch extra in case some are duds
            if fmp_news and len(fmp_news) >= 3:
                for item in fmp_news[:n]:
                    if item.get("title"):
                        result.append({
                            "title": item["title"],
                            "publisher": item.get("source", ""),
                            "url": item.get("url", ""),
                            "time": item.get("time", ""),
                            "summary": item.get("summary", ""),
                            "symbol": item.get("symbol", ""),
                        })
                source_used = "fmp"
                logger.debug("Market news: got %d items from FMP", len(result))
    except Exception as exc:
        logger.debug("FMP market news failed: %s", exc)

    # ── Source 2: Finnhub general news (if FMP returned < 5 items) ──────────
    if len(result) < 5:
        try:
            from nq_data.finnhub import get_finnhub_client
            import httpx as _httpx
            from datetime import datetime as _dt, timezone as _tz
            fh = get_finnhub_client()
            if fh._enabled:
                # Finnhub general market news: GET /api/v1/news?category=general
                from_ts = int(time.time()) - 7 * 86400
                to_ts = int(time.time())
                params = {
                    "category": "general",
                    "token": fh._api_key,
                    "from": from_ts,
                    "to": to_ts,
                }
                from nq_data.broker import broker as _broker
                with _broker.acquire("finnhub"):
                    resp = _httpx.Client(timeout=10.0).get(
                        "https://finnhub.io/api/v1/news", params=params
                    )
                if resp.status_code == 200:
                    fh_news = resp.json()
                    if fh_news and isinstance(fh_news, list):
                        for item in fh_news:
                            if len(result) >= n:
                                break
                            title = item.get("headline", "")
                            if not title:
                                continue
                            # Avoid duplicates by title
                            existing_titles = {r["title"] for r in result}
                            if title in existing_titles:
                                continue
                            pub_ts = item.get("datetime", 0)
                            pub_date = ""
                            if pub_ts:
                                try:
                                    pub_date = _dt.fromtimestamp(int(pub_ts), tz=_tz.utc).isoformat()
                                except (ValueError, OSError):
                                    pub_date = str(pub_ts)
                            result.append({
                                "title": title,
                                "publisher": item.get("source", ""),
                                "url": item.get("url", ""),
                                "time": pub_date,
                                "summary": item.get("summary", ""),
                                "symbol": item.get("related", ""),
                            })
                        source_used = source_used or "finnhub"
                        logger.debug("Market news: supplemented to %d items with Finnhub", len(result))
        except Exception as exc:
            logger.debug("Finnhub market news failed: %s", exc)

    # ── Source 3: yfinance (only on non-Render, as last resort) ─────────────
    if len(result) < 5 and not _IS_RENDER:
        items = []
        for attempt in range(2):
            try:
                items = yf.Ticker("^GSPC", session=_get_yf_session()).news or []
                break
            except Exception as exc:
                if _is_yf_crumb_error(exc) and attempt == 0:
                    logger.warning("market_news crumb error, resetting session and retrying")
                    _reset_yf_session()
                    continue
                logger.debug("Market news yfinance fetch failed: %s", exc)
                break
        try:
            for item in items:
                if len(result) >= n:
                    break
                content = item.get("content") or {}
                title = content.get("title") or item.get("title", "")
                if not title:
                    continue
                # Avoid duplicates
                existing_titles = {r["title"] for r in result}
                if title in existing_titles:
                    continue
                publisher = (
                    (content.get("provider") or {}).get("displayName")
                    or item.get("publisher", "")
                )
                url = (
                    (content.get("canonicalUrl") or {}).get("url")
                    or item.get("link", "")
                )
                pub_date = content.get("pubDate") or str(item.get("providerPublishTime", ""))
                result.append(
                    {"title": title, "publisher": publisher, "url": url, "time": pub_date}
                )
            source_used = source_used or "yfinance"
            logger.debug("Market news: supplemented to %d items with yfinance", len(result))
        except Exception as exc:
            logger.debug("Market news yfinance parse failed: %s", exc)

    # ── Return results ──────────────────────────────────────────────────────
    _news_cache = {"news": result}
    _news_ts = time.time()
    return {"news": result, "source": source_used}


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


def _snap_to_mover(snap: dict) -> dict:
    return {
        "ticker": snap.get("ticker", ""),
        "name": snap.get("company_name") or snap.get("ticker", ""),
        "price": snap.get("price"),
        "change_pct": snap.get("change_pct"),
        "change_abs": None,
        "volume": snap.get("volume"),
    }


@router.get("/movers")
async def market_movers(market: str = Query("US", description="Market filter: US, IN, or ALL")):
    mkt_filter = market.upper() if market else "US"
    # ── Fast path: stock_snapshot (no external API calls) ────────────────
    try:
        from nq_api.cache.snapshot_cache import read_all_by_market, is_stale
        all_snaps: list[dict] = []
        markets_to_fetch = [mkt_filter] if mkt_filter not in ("ALL", "") else ("US", "IN")
        for mkt in (markets_to_fetch if isinstance(markets_to_fetch, list) else [markets_to_fetch]):
            snaps = await asyncio.to_thread(read_all_by_market, mkt, limit=500)
            if snaps:
                all_snaps.extend(snaps)
        # If specific market had too few results, fall back to both markets
        if len(all_snaps) < 3 and mkt_filter not in ("ALL", ""):
            for mkt in ("US", "IN"):
                snaps = await asyncio.to_thread(read_all_by_market, mkt, limit=500)
                if snaps:
                    all_snaps.extend(snaps)
        if all_snaps:
            # Allow change_pct=None (treat as 0) — stale snapshots ok if price exists
            valid = [
                s for s in all_snaps
                if s.get("price") is not None
                and not is_stale(s, 120)  # 2-hour grace for weekend/off-hours
            ]
            if len(valid) >= 3:
                sorted_by_change = sorted(
                    valid,
                    key=lambda x: x.get("change_pct") if x.get("change_pct") is not None else 0,
                    reverse=True,
                )
                gainers = [_snap_to_mover(s) for s in sorted_by_change[:5]]
                losers = [_snap_to_mover(s) for s in list(reversed(sorted_by_change[-5:]))]
                active = [_snap_to_mover(s) for s in sorted(valid, key=lambda x: x.get("volume") or 0, reverse=True)[:5]]
                return {"gainers": gainers, "losers": losers, "active": active, "market": mkt_filter}
            # Not enough FRESH snapshots (off-hours: last refresh >2h ago) → rank the
            # stale-but-real rows by change_pct. A slightly stale real mover beats a
            # price-sorted placeholder, and ranking the full universe (~500 rows) keeps
            # gainers/losers from collapsing to the same reversed list (the old by-price
            # path returned identical tickers as both gainers and losers).
            if len(all_snaps) >= 3:
                priced = [s for s in all_snaps if s.get("price") is not None]
                by_chg = sorted(
                    priced,
                    key=lambda x: x.get("change_pct") if x.get("change_pct") is not None else 0,
                    reverse=True,
                )
                gainers = [_snap_to_mover(s) for s in by_chg[:5]]
                losers = [_snap_to_mover(s) for s in list(reversed(by_chg[-5:]))]
                active = [_snap_to_mover(s) for s in sorted(priced, key=lambda x: x.get("volume") or 0, reverse=True)[:5]]
                return {"gainers": gainers, "losers": losers, "active": active, "market": mkt_filter, "stale": True}
    except Exception as exc:
        logger.debug("movers snapshot fast path failed: %s", exc)

    # ── Fallback: existing FMP + yfinance logic ─────────────────────────
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
    _fmp_partial = None  # saved when FMP returns partial results
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
                    # Skip items with missing price or micro-penny stocks (<$0.10)
                    if price is None:
                        return None
                    try:
                        p = float(price)
                        if p < 0.10:
                            return None  # Sub-dollar stocks are unreliable
                    except (ValueError, TypeError):
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
                def _build_category(raw, label):
                    """Build mover list; if all filtered out, fall back to raw data with stale flag."""
                    filtered = [x for x in (_to_mover(m) for m in raw[:50]) if x][:5]
                    if not filtered and raw:
                        logger.warning("FMP %s: all filtered out (%d raw), using unfiltered stale data", label, len(raw))
                        filtered = [
                            {
                                "ticker": m.get("ticker", ""),
                                "name": m.get("name", ""),
                                "price": m.get("price"),
                                "change_pct": m.get("change_pct"),
                                "change_abs": m.get("change"),
                                "volume": m.get("volume"),
                                "stale": True,
                            }
                            for m in raw[:5]
                        ]
                    return filtered
                result = {
                    "gainers": _build_category(gainers, "gainers"),
                    "losers": _build_category(losers, "losers"),
                    "active": _build_category(actives, "active"),
                }
                if result["gainers"] or result["losers"] or result["active"]:
                    _movers_cache = result
                    _movers_ts = time.time()
                    return result
                # Should not reach here now, but keep as safety net
                if not result["gainers"]:
                    logger.warning("FMP gainers: empty after all processing (%d raw)", len(gainers))
                if not result["losers"]:
                    logger.warning("FMP losers: empty after all processing (%d raw)", len(losers))
                # Save partial FMP result for merge after yfinance fallback
                _fmp_partial = result
            else:
                logger.warning("FMP movers returned empty for all categories")
    except Exception as exc:
        logger.warning("FMP market movers failed: %s — falling back to yfinance", exc)

    # Fallback: FMP batch quotes for _MOVERS_UNIVERSE (single API call, no rate limits)
    rows = []
    try:
        from nq_data.fmp import get_fmp_client
        fmp = get_fmp_client()
        if fmp._enabled:
            batch = fmp.get_batch_quotes(list(_MOVERS_UNIVERSE))
            if batch:
                for sym, quote in batch.items():
                    price = quote.get("price")
                    # Only skip items with missing/None price — allow price=0
                    # (stale after-hours/weekend data still useful for context)
                    if price is None:
                        continue
                    try:
                        float(price)
                    except (ValueError, TypeError):
                        continue
                    chg_pct = float(quote.get("change_pct") or 0)
                    chg_abs = float(quote.get("change") or 0)
                    vol = quote.get("volume")
                    rows.append({
                        "ticker": sym,
                        "name": sym,
                        "price": round(float(price), 2),
                        "change_pct": chg_pct,
                        "change_abs": chg_abs,
                        "volume": vol,
                    })
    except Exception as exc:
        logger.warning("FMP batch quotes movers fallback failed: %s", exc)

    if rows:
        rows_sorted = sorted(rows, key=lambda x: x["change_pct"], reverse=True)
        result = {
            "gainers": rows_sorted[:5],
            "losers": list(reversed(rows_sorted[-5:])),
            "active": sorted(rows, key=lambda x: x["volume"] or 0, reverse=True)[:5],
        }
        # Merge FMP partial results (keep FMP active if we had it)
        if _fmp_partial:
            if _fmp_partial.get("active"):
                result["active"] = _fmp_partial["active"]
            if _fmp_partial.get("gainers"):
                result["gainers"] = _fmp_partial["gainers"]
            if _fmp_partial.get("losers"):
                result["losers"] = _fmp_partial["losers"]
        _movers_cache = result
        _movers_ts = time.time()
        return result
    logger.warning("FMP movers universe fallback returned 0 valid rows")

    # ── Last resort: read from stock_snapshot directly ────────────────
    try:
        from nq_api.cache.snapshot_cache import read_all_by_market
        for mkt in ("US", "IN"):
            snaps = read_all_by_market(mkt, limit=200)
            if snaps:
                priced = [s for s in snaps if s.get("price") is not None]
                if len(priced) >= 3:
                    by_price = sorted(priced, key=lambda x: x.get("price") or 0, reverse=True)
                    top5 = [_snap_to_mover(s) for s in by_price[:5]]
                    result = {"gainers": top5, "losers": list(reversed(top5)), "active": top5, "stale": True}
                    _movers_cache = result
                    _movers_ts = time.time()
                    logger.info("Movers: served from snapshot last-resort (%s market, %d rows)", mkt, len(priced))
                    return result
    except Exception as exc:
        logger.debug("movers snapshot last-resort failed: %s", exc)

    # ── Return stale cache if available, otherwise error ────────────────
    if _movers_cache:
        result = {**_movers_cache, "stale": True}
        if _fmp_partial and _fmp_partial.get("active"):
            result["active"] = _fmp_partial["active"]
        logger.warning("Movers: all sources failed, returning stale cache (age=%ds)", int(time.time() - _movers_ts))
        return result
    result = {"gainers": [], "losers": [], "active": []}
    if _fmp_partial:
        if _fmp_partial.get("active"):
            result["active"] = _fmp_partial["active"]
        if _fmp_partial.get("gainers"):
            result["gainers"] = _fmp_partial["gainers"]
        if _fmp_partial.get("losers"):
            result["losers"] = _fmp_partial["losers"]
    if not any(result.values()):
        result["error"] = "All data sources failed"
    return result


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


@router.get("/trending")
async def trending_tickers(
    limit: int = 10,
    market: str = "US",
):
    """Top tickers analyzed today — based on recent QuantFactor IRS scores."""
    import os
    import httpx as _hx

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return {"trending": [], "market": market}

    endpoint = f"{url}/rest/v1/quantfactor_universe"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }

    try:
        with _hx.Client(timeout=10) as client:
            r = client.get(
                endpoint,
                params={
                    "select": "ticker,market,sector,irs_pct,g_score,risk_eff_score",
                    "market": f"eq.{market}",
                    "irs_pct": "not.is.null",
                    "order": "irs_pct.desc",
                    "limit": str(limit),
                },
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        logging.getLogger(__name__).warning("Trending fetch failed: %s", exc)
        data = []

    return {
        "trending": data if isinstance(data, list) else [],
        "market": market,
        "count": len(data) if isinstance(data, list) else 0,
    }
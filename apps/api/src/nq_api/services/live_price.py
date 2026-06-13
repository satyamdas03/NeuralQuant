"""Single source of truth for a ticker's current price on Render.

Source order: nq-openbb yfinance proxy (works on Render for US + IN) ->
stock_snapshot (30-min refresh) -> score_cache (7d). 60s in-process cache.
"""
from __future__ import annotations

import logging
import time

from nq_data.openbb import get_openbb_client, _obb_symbol
from nq_api.cache.snapshot_cache import read_snapshot

log = logging.getLogger(__name__)

_CACHE: dict[tuple[str, str], tuple[float, float]] = {}
_TTL_S = 60.0


def _openbb_price(ticker: str, market: str) -> float | None:
    try:
        obb = get_openbb_client()
        if not obb.enabled:
            return None
        q = obb.get_quote(_obb_symbol(ticker, market))
        if not q:
            return None
        for field in ("last_price", "price", "close", "prev_close"):
            v = q.get(field)
            if v:
                p = float(v)
                if p > 0:
                    return p
    except Exception:
        log.debug("openbb price failed for %s/%s", ticker, market, exc_info=True)
    return None


def _score_cache_price(ticker: str, market: str) -> float | None:
    try:
        from nq_api.cache.score_cache import read_one
        sc = read_one(ticker.upper(), market, max_age_seconds=604800)  # 7d
        if sc and sc.get("current_price"):
            p = float(sc["current_price"])
            return p if p > 0 else None
    except Exception:
        return None
    return None


def get_live_price(ticker: str, market: str = "US") -> tuple[float | None, str | None]:
    """Return (price, source) for the ticker, or (None, None) if all sources miss."""
    key = (ticker.upper(), market)
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _TTL_S:
        return hit[1], "cache"

    p = _openbb_price(ticker, market)
    source = "openbb"
    if not p:
        snap = read_snapshot(ticker.upper(), market)
        p = float(snap["price"]) if snap and snap.get("price") and float(snap["price"]) > 0 else None
        source = "stock_snapshot"
    if not p:
        p = _score_cache_price(ticker, market)
        source = "score_cache_7d"

    if p:
        _CACHE[key] = (now, p)
        return p, source
    return None, None

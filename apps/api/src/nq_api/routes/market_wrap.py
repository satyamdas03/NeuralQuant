"""Daily Market Wrap — JSON-only after email removal.

This module provides:
1. GET /market-wrap/today — Return the daily market wrap data as JSON

Email broadcast endpoints have been removed. No emails are sent.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from nq_api.auth.models import User
from nq_api.auth.rate_limit import get_current_user
from nq_api.auth.deps import get_current_user_optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market-wrap", tags=["market-wrap"])


def _get_watchlist_scores(user_id: str, market: str, limit: int = 5) -> list[dict]:
    """Fetch score_cache entries for tickers in a user's watchlist."""
    from nq_api.cache.score_cache import _supabase_rest
    from nq_api.routes.market import _batch_pct_change

    try:
        watchlist = _supabase_rest(
            "watchlists",
            method="GET",
            query={
                "user_id": f"eq.{user_id}",
                "market": f"eq.{market}",
                "select": "ticker",
            },
        )
    except Exception:
        logger.debug("Failed to fetch watchlist for user %s", user_id)
        return []

    if not watchlist:
        return []

    tickers = [w["ticker"] for w in watchlist if w.get("ticker")]
    if not tickers:
        return []

    # Fetch live price changes for watchlist tickers.
    # IN tickers MUST carry the .NS suffix — bare names ('RELIANCE', 'TCS') make
    # yfinance treat them as US symbols and it rate-limits / reports "possibly
    # delisted". Resolve to .NS for the fetch, then map results back to bare keys
    # so the downstream score_cache lookup (which uses bare tickers) still works.
    def _yf_sym(t: str) -> str:
        return f"{t}.NS" if market == "IN" and "." not in t else t

    raw_changes = _batch_pct_change([_yf_sym(t) for t in tickers])
    price_changes = {t: raw_changes.get(_yf_sym(t), {}) for t in tickers}

    # PostgREST IN filter — match score_cache rows for exactly the watchlist
    # tickers (bare, no .NS — that's how score_cache stores them), scoped to the
    # requested market.
    try:
        scores = _supabase_rest(
            "score_cache",
            method="GET",
            query={
                "ticker": f"in.({','.join(tickers)})",
                "market": f"eq.{market}",
                "select": "ticker,composite_score,sector,current_price,long_name",
                "order": "composite_score.desc",
                "limit": str(limit),
            },
        )
    except Exception:
        logger.debug("Failed to fetch watchlist scores for user %s", user_id)
        return []

    if not scores:
        return []

    def _verdict(score: float) -> str:
        if score >= 7.5:
            return "STRONG BUY"
        if score >= 6.0:
            return "BUY"
        if score >= 4.5:
            return "HOLD"
        if score >= 3.0:
            return "SELL"
        return "STRONG SELL"

    for row in scores:
        ticker = row.get("ticker", "")
        pc = price_changes.get(ticker, {})
        row["change_pct"] = pc.get("change_pct")
        # composite_score is ~0-100; derive a clean 0-10 score for display + verdict.
        comp = row.get("composite_score")
        row["score_1_10"] = max(0, min(10, round(float(comp) / 10))) if comp is not None else 0
        row["verdict"] = _verdict(float(row["score_1_10"]))

    return scores


def market_label(market: str) -> str:
    return "NIFTY 500" if market == "IN" else "S&P 500"


@router.get("/today")
async def get_today_market_wrap(
    market: str = "US",
    user: User | None = Depends(get_current_user_optional),
):
    """Return the daily market wrap data as JSON (for frontend display).

    When user is authenticated, includes personalized watchlist highlights.
    """
    from nq_api.routes.market import _market_overview_sync
    from nq_api.cache.score_cache import read_top_picks

    try:
        market_data = await asyncio.wait_for(
            asyncio.to_thread(_market_overview_sync, market),
            timeout=20.0,
        )
    except asyncio.TimeoutError:
        logger.warning("Market wrap today: _market_overview_sync timed out for %s", market)
        # Return stub indices so frontend never shows "unavailable"
        if market == "IN":
            market_data = {
                "indices": [
                    {"symbol": "^NSEI", "name": "Nifty 50", "price": 0.0, "change_pct": 0.0, "change_abs": 0.0},
                    {"symbol": "^BSESN", "name": "Sensex", "price": 0.0, "change_pct": 0.0, "change_abs": 0.0},
                ],
                "futures": [],
            }
        else:
            market_data = {
                "indices": [
                    {"symbol": "^GSPC", "name": "S&P 500", "price": 0.0, "change_pct": 0.0, "change_abs": 0.0},
                    {"symbol": "^IXIC", "name": "NASDAQ", "price": 0.0, "change_pct": 0.0, "change_abs": 0.0},
                ],
                "futures": [],
            }
    except Exception:
        logger.exception("Market wrap today: failed to fetch market data")
        market_data = {"indices": [], "futures": []}

    try:
        top_picks = read_top_picks(market=market, limit=5)
    except Exception:
        logger.exception("Market wrap today: failed to fetch top picks")
        top_picks = []

    # Personalized watchlist highlights for authenticated users
    watchlist_picks: list[dict] = []
    if user is not None:
        try:
            watchlist_picks = _get_watchlist_scores(user.id, market, limit=5)
        except Exception:
            logger.debug("Market wrap today: failed to fetch watchlist for %s", user.id)

    return {
        "date": datetime.now(timezone.utc).strftime("%A, %B %d, %Y"),
        "market": market,
        "market_label": market_label(market),
        "indices": market_data.get("indices", []),
        "top_picks": top_picks,
        "watchlist_picks": watchlist_picks,
    }

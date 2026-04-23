"""GET /smart-money — live insider trading tracker.

Aggregates SEC EDGAR Form 4 filings across a rotating watch-list of
large/mid-cap US tickers.  Returns recent transactions, most-bought
and most-sold tables, and an overall Smart-Money sentiment gauge.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter

router = APIRouter()
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_SMART_MONEY_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "BRK-B", "JPM", "V", "MA", "UNH", "XOM", "JNJ", "HD",
    "COST", "ABBV", "LLY", "CVX", "BAC", "NFLX", "ORCL",
    "ADBE", "CRM", "AMD", "AVGO", "WMT", "MCD", "PFE",
    "ISRG", "PLTR",
]
_LOOKBACK_DAYS = 90
_SMART_CACHE: dict[str, Any] | None = None
_SMART_TS: float = 0.0
SMART_TTL = 600  # 10 minutes


def _fetch_insider_blocking(ticker: str) -> list[dict[str, Any]]:
    """Blocking fetch of Form 4 events for a single ticker."""
    try:
        from nq_data.alt_signals.edgar_form4 import Form4Connector
        end = date.today()
        start = end - timedelta(days=_LOOKBACK_DAYS)
        events = Form4Connector().get_insider_events(ticker, start, end)
        # Enrich each event
        for e in events:
            e["ticker"] = ticker
            # Ensure price is float
            try:
                e["price"] = float(e.get("price") or 0.0)
            except (ValueError, TypeError):
                e["price"] = 0.0
            try:
                e["shares"] = float(e.get("shares") or 0.0)
            except (ValueError, TypeError):
                e["shares"] = 0.0
            e["officer_title"] = e.get("officer_title") or "Officer"
            e["insider_name"] = e.get("insider_name") or "Unknown"
            e["value"] = e["price"] * e["shares"]
        return events
    except Exception as exc:
        log.warning("Smart-money fetch failed for %s: %s", ticker, exc)
        return []


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------
def _aggregate(all_events: list[dict[str, Any]]) -> dict[str, Any]:
    transactions = sorted(
        [e for e in all_events if e.get("is_purchase") is not None],
        key=lambda x: x.get("file_date") or "",
        reverse=True,
    )[:50]

    # Most bought / sold by ticker
    ticker_buy: dict[str, float] = {}
    ticker_sell: dict[str, float] = {}
    for e in all_events:
        t = e.get("ticker", "")
        val = e.get("value", 0.0)
        if e.get("is_purchase"):
            ticker_buy[t] = ticker_buy.get(t, 0.0) + val
        else:
            ticker_sell[t] = ticker_sell.get(t, 0.0) + val

    most_bought = [
        {"ticker": t, "total_value": round(v, 2)}
        for t, v in sorted(ticker_buy.items(), key=lambda x: x[1], reverse=True)[:5]
        if v > 0
    ]
    most_sold = [
        {"ticker": t, "total_value": round(v, 2)}
        for t, v in sorted(ticker_sell.items(), key=lambda x: x[1], reverse=True)[:5]
        if v > 0
    ]

    # Overall sentiment gauge
    buy_val = sum(ticker_buy.values())
    sell_val = sum(ticker_sell.values())
    total = buy_val + sell_val
    if total == 0:
        sentiment = "neutral"
        sentiment_score = 0.5
    else:
        ratio = buy_val / total
        sentiment_score = ratio
        if ratio >= 0.6:
            sentiment = "bullish"
        elif ratio <= 0.4:
            sentiment = "bearish"
        else:
            sentiment = "neutral"

    return {
        "sentiment": sentiment,
        "sentiment_score": round(sentiment_score, 2),
        "transactions": transactions,
        "most_bought": most_bought,
        "most_sold": most_sold,
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------
@router.get("/smart-money")
async def get_smart_money() -> dict[str, Any]:
    """Return aggregated insider trading data across the US universe."""
    global _SMART_CACHE, _SMART_TS
    if _SMART_CACHE and time.time() - _SMART_TS < SMART_TTL:
        return _SMART_CACHE

    # Fetch in parallel — EDGAR is slow; cap batch + enforce timeout
    batch = _SMART_MONEY_UNIVERSE[:6]
    try:
        results = await asyncio.wait_for(
            asyncio.gather(
                *[asyncio.to_thread(_fetch_insider_blocking, sym) for sym in batch],
                return_exceptions=True,
            ),
            timeout=20,
        )
    except asyncio.TimeoutError:
        results = []

    all_events: list[dict[str, Any]] = []
    for r in results:
        if isinstance(r, list):
            all_events.extend(r)
        else:
            log.warning("Smart-money batch error: %s", r)

    payload = _aggregate(all_events)
    _SMART_CACHE = payload
    _SMART_TS = time.time()
    return payload

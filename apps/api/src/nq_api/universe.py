# apps/api/src/nq_api/universe.py
"""Stock universes loaded from data/universe JSON.

Phase 4 Pillar B: 500 US (S&P 500) + 200 IN (Nifty 200) with GICS/NSE sector labels.
Falls back to hardcoded mini list if JSON files absent (dev convenience).
"""
from __future__ import annotations
import json
from pathlib import Path
from functools import lru_cache
import logging
logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[4]  # apps/api/src/nq_api/universe.py -> repo root
_UNIVERSE_DIR = _REPO_ROOT / "data" / "universe"

# Fallback small universes for dev if JSON missing
_US_FALLBACK = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
    "JPM", "V", "MA", "UNH", "XOM", "JNJ", "PG", "HD", "COST", "ABBV",
    "MRK", "LLY", "CVX", "BAC", "NFLX", "ORCL", "ADBE", "CRM", "AMD",
    "INTC", "QCOM", "TXN", "AVGO", "MU", "AMAT", "LRCX", "KLAC",
    "WMT", "TGT", "NKE", "MCD", "SBUX", "DIS", "CMCSA", "T", "VZ",
    "PFE", "AMGN", "GILD", "REGN", "ISRG",
]
_IN_FALLBACK = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR", "ICICIBANK",
    "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "HCLTECH", "WIPRO",
    "ASIANPAINT", "MARUTI", "SUNPHARMA", "ULTRACEMCO", "BAJFINANCE",
    "TITAN", "NESTLEIND", "POWERGRID", "NTPC", "ONGC", "COALINDIA",
    "TATASTEEL", "JSWSTEEL", "HINDALCO", "ADANIPORTS", "ADANIENT",
    "DMART", "PIDILITIND", "EICHERMOT", "BAJAJ-AUTO", "HEROMOTOCO",
    "M&M", "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP",
]


def _load_json(path: Path) -> list[dict] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.debug("Non-critical enrichment failed: %s", e)
        return None


@lru_cache(maxsize=1)
def _load_universe_full() -> dict[str, list[dict]]:
    us = _load_json(_UNIVERSE_DIR / "us_sp500.json")
    ind = _load_json(_UNIVERSE_DIR / "in_nifty200.json")
    us_rows = us if us else [{"ticker": t, "name": t, "sector": "Unknown", "subindustry": "Unknown", "market_cap_bucket": "unknown"} for t in _US_FALLBACK]
    in_rows = ind if ind else [{"ticker": t, "name": t, "sector": "Unknown", "subindustry": "Unknown", "market_cap_bucket": "unknown"} for t in _IN_FALLBACK]
    return {"US": us_rows, "IN": in_rows}


UNIVERSE_FULL: dict[str, list[dict]] = _load_universe_full()

US_DEFAULT: list[str] = [r["ticker"] for r in UNIVERSE_FULL["US"]]
IN_DEFAULT: list[str] = [r["ticker"] for r in UNIVERSE_FULL["IN"]]

UNIVERSE_BY_MARKET: dict[str, list[str]] = {
    "US": US_DEFAULT,
    "IN": IN_DEFAULT,
    "GLOBAL": US_DEFAULT + IN_DEFAULT,
}


@lru_cache(maxsize=2048)
def sector_of(ticker: str, market: str = "US") -> str:
    """Return GICS/NSE sector for ticker; 'Unknown' if not in universe."""
    for row in UNIVERSE_FULL.get(market, []):
        if row["ticker"] == ticker:
            return row.get("sector") or "Unknown"
    # search both markets as fallback
    for m in ("US", "IN"):
        for row in UNIVERSE_FULL.get(m, []):
            if row["ticker"] == ticker:
                return row.get("sector") or "Unknown"
    return "Unknown"

"""Read/write helpers for public.score_cache.

Populated by scripts/nightly_score.py (nightly GHA).
Read by /screener for sub-100ms responses.
"""
from __future__ import annotations
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any

from dotenv import load_dotenv
from pathlib import Path
import httpx


log = logging.getLogger(__name__)
_env_loaded = False
_known_columns: set[str] | None = None


def _load_env():
    """Load .env once (idempotent)."""
    global _env_loaded
    if _env_loaded:
        return
    env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(env_path, override=True)
    _env_loaded = True


def _supabase_rest(
    table: str,
    method: str = "GET",
    query: dict | None = None,
    body: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]] | dict[str, Any] | None:
    """Direct REST call to Supabase PostgREST API (bypasses supabase-py)."""
    _load_env()
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return None

    endpoint = f"{url}/rest/v1/{table}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    try:
        with httpx.Client(timeout=10) as client:
            if method == "GET":
                r = client.get(endpoint, params=query or {}, headers=headers)
            elif method == "POST":
                r = client.post(endpoint, json=body, headers=headers)
            elif method == "PATCH":
                r = client.patch(endpoint, json=body, params=query or {}, headers=headers)
            else:
                return None
            r.raise_for_status()
            return r.json() if r.content else None
    except Exception as e:
        log.warning("Supabase REST call failed for table=%s: %s", table, e)
        return None


def _get_known_columns() -> set[str]:
    """Fetch actual column names from score_cache table. Caches result."""
    global _known_columns
    if _known_columns is not None:
        return _known_columns
    # Fetch one row to discover columns
    data = _supabase_rest("score_cache", "GET", {"select": "*", "limit": "1"})
    if isinstance(data, list) and data:
        _known_columns = set(data[0].keys())
    else:
        # Table might be empty — use known schema
        _known_columns = {
            "ticker", "market", "sector", "composite_score", "rank_score",
            "value_percentile", "momentum_percentile", "quality_percentile",
            "low_vol_percentile", "short_interest_percentile", "current_price",
            "analyst_target", "pe_ttm", "market_cap", "week52_high", "week52_low",
            "pb_ratio", "beta", "long_name", "industry", "analyst_rec",
            "earnings_date", "dividend_yield",
            "computed_at",
        }
    log.info("score_cache columns: %s", sorted(_known_columns))
    return _known_columns


def _reset_known_columns():
    """Force re-fetch of column list after schema migration."""
    global _known_columns
    _known_columns = None


def read_top(
    market: str,
    n: int = 50,
    max_age_seconds: int = 3600,
) -> list[dict[str, Any]]:
    """Return top-n scored tickers for market if cache fresh, else []."""
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)).isoformat()
    data = _supabase_rest(
        "score_cache",
        method="GET",
        query={
            "select": "*",
            "market": f"eq.{market}",
            "computed_at": f"gte.{cutoff}",
            "order": "composite_score.desc",
            "limit": str(n),
        },
    )
    return data if isinstance(data, list) else []


def read_top_picks(
    market: str = "US",
    limit: int = 5,
    max_age_days: int = 7,
) -> list[dict[str, Any]]:
    """Return top-scored tickers with score and sector for market wrap emails."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
    data = _supabase_rest(
        "score_cache",
        method="GET",
        query={
            "select": "ticker,composite_score,sector",
            "market": f"eq.{market}",
            "composite_at": f"gte.{cutoff}",
            "order": "composite_score.desc",
            "limit": str(limit),
        },
    )
    return data if isinstance(data, list) else []


def upsert_scores(rows: list[dict[str, Any]]) -> int:
    """Batch upsert rows keyed on (ticker, market). Returns count."""
    if not rows:
        return 0
    known = _get_known_columns()
    now_iso = datetime.now(timezone.utc).isoformat()
    for r in rows:
        r.setdefault("computed_at", now_iso)
    # Filter to only columns that exist in the table (PostgREST rejects unknown columns)
    filtered = [{k: v for k, v in r.items() if k in known} for r in rows]
    result = _supabase_rest("score_cache", method="POST", body=filtered)
    return len(rows) if result is not None else 0


def read_one(
    ticker: str,
    market: str,
    max_age_seconds: int = 7200,
) -> dict[str, Any] | None:
    """Return a single ticker's cached score if fresh, else None."""
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)).isoformat()
    data = _supabase_rest(
        "score_cache",
        method="GET",
        query={
            "select": "*",
            "ticker": f"eq.{ticker.upper()}",
            "market": f"eq.{market}",
            "computed_at": f"gte.{cutoff}",
            "limit": "1",
        },
    )
    if isinstance(data, list) and data:
        return data[0]
    return None


def age_seconds(market: str) -> int | None:
    """Return seconds since newest computed_at for market, or None if empty."""
    data = _supabase_rest(
        "score_cache",
        method="GET",
        query={
            "select": "computed_at",
            "market": f"eq.{market}",
            "order": "computed_at.desc",
            "limit": "1",
        },
    )
    if isinstance(data, list) and data:
        ts = datetime.fromisoformat(data[0]["computed_at"].replace("Z", "+00:00"))
        return int((datetime.now(timezone.utc) - ts).total_seconds())
    return None


def read_sector_median(
    sector: str,
    market: str,
    fields: tuple[str, ...] = (
        "pe_ttm", "pb_ratio", "gross_profit_margin", "roe",
        "fcf_yield", "debt_equity", "revenue_growth_yoy", "composite_score",
        "quality_percentile", "momentum_percentile",
    ),
    max_age_seconds: int = 86400,
) -> dict[str, float | None]:
    """Return median values for a sector from score_cache.

    Used for peer comparison context in Ask AI and PARA-DEBATE.
    Returns {field: median_value} for the given sector/market.
    """
    from nq_api.universe import UNIVERSE_FULL
    # Find tickers in this sector
    tickers_in_sector = [
        row["ticker"] for row in UNIVERSE_FULL.get(market, [])
        if row.get("sector") == sector
    ]
    if not tickers_in_sector:
        return {}

    # Fetch all fresh rows for this market
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)).isoformat()
    data = _supabase_rest(
        "score_cache",
        method="GET",
        query={
            "select": ",".join(["ticker"] + list(fields)),
            "market": f"eq.{market}",
            "computed_at": f"gte.{cutoff}",
        },
    )
    if not isinstance(data, list) or not data:
        return {}

    # Filter to sector tickers
    sector_set = set(tickers_in_sector)
    sector_rows = [r for r in data if r.get("ticker") in sector_set]
    if not sector_rows:
        return {}

    # Compute medians
    import statistics
    result: dict[str, float | None] = {}
    for field in fields:
        values = []
        for row in sector_rows:
            v = row.get(field)
            if v is not None:
                try:
                    values.append(float(v))
                except (ValueError, TypeError):
                    pass
        result[field] = statistics.median(values) if values else None
    return result


# ── Enrichment cache (1-hour TTL) ────────────────────────────────────────────
# Stores RSI/MACD/ATR/SMA/insider/news data per ticker so subsequent requests
# hit Supabase instead of re-computing from yfinance/Finnhub (which takes 5-30s).

_ENRICHMENT_TTL = 3600  # 1 hour


def read_enrichment(ticker: str, market: str) -> dict[str, Any] | None:
    """Return cached enrichment data if fresh (< 1 hour), else None."""
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=_ENRICHMENT_TTL)).isoformat()
    data = _supabase_rest(
        "enrichment_cache",
        method="GET",
        query={
            "select": "*",
            "ticker": f"eq.{ticker.upper()}",
            "market": f"eq.{market}",
            "cached_at": f"gte.{cutoff}",
            "limit": "1",
        },
    )
    if isinstance(data, list) and data:
        row = data[0]
        # Remove metadata fields, return only enrichment data
        for meta_key in ("id", "ticker", "market", "cached_at"):
            row.pop(meta_key, None)
        # Remove None values — callers expect missing keys, not None
        return {k: v for k, v in row.items() if v is not None}
    return None


def write_enrichment(ticker: str, market: str, data: dict[str, Any]) -> bool:
    """Store enrichment data in Supabase. Returns True on success."""
    if not data:
        return False
    row = {"ticker": ticker.upper(), "market": market, "cached_at": datetime.now(timezone.utc).isoformat()}
    # Only store JSON-serializable values (float, int, str, bool, None)
    for k, v in data.items():
        if isinstance(v, (int, float, str, bool)) or v is None:
            row[k] = v
        elif isinstance(v, dict):
            import json
            row[k] = json.dumps(v)
    # Filter out keys that don't exist in the table (will be created on first upsert)
    # Use POST with Prefer: return=representation for upsert
    _load_env()
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return False
    endpoint = f"{url}/rest/v1/enrichment_cache"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation,resolution=merge-duplicates",
    }
    try:
        with httpx.Client(timeout=10) as client:
            r = client.post(endpoint, json=row, headers=headers)
            r.raise_for_status()
            log.info("Cached enrichment for %s/%s: %d fields", ticker, market, len(data))
            return True
    except Exception as e:
        log.warning("Failed to cache enrichment for %s/%s: %s", ticker, market, e)
        return False

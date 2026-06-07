"""Read/write helpers for public.stock_snapshot.

One table for ALL live stock data: prices, fundamentals, enrichment.
Refresh: every 30 minutes via GitHub Actions → market_refresh.py
"""
from __future__ import annotations
import logging
import math
import os
from datetime import datetime, timezone, timedelta
from typing import Any

from dotenv import load_dotenv
from pathlib import Path
import httpx


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers (mirrors score_cache.py pattern)
# ---------------------------------------------------------------------------

def _is_nonfinite(v) -> bool:
    try:
        import pandas as pd
        if pd.isna(v) and v is not None and v is not False:
            return True
    except Exception:
        pass
    if isinstance(v, float):
        return math.isnan(v) or math.isinf(v)
    if hasattr(v, '__float__') and not isinstance(v, (str, int, bool, type(None))):
        try:
            fv = float(v)
            return math.isnan(fv) or math.isinf(fv)
        except (TypeError, ValueError):
            pass
    return False


def _sanitize_floats(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if _is_nonfinite(v):
            out[k] = None
        elif isinstance(v, dict):
            out[k] = _sanitize_floats(v)
        elif isinstance(v, list):
            out[k] = [
                _sanitize_floats(i) if isinstance(i, dict)
                else (None if _is_nonfinite(i) else i)
                for i in v
            ]
        elif hasattr(v, '__float__') and not isinstance(v, (str, int, bool, type(None))):
            try:
                fv = float(v)
                out[k] = None if _is_nonfinite(fv) else fv
            except (TypeError, ValueError):
                out[k] = v
        else:
            out[k] = v
    return out


_env_loaded = False
_known_columns: set[str] | None = None


def _load_env():
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
    body: list[dict[str, Any]] | dict[str, Any] | None = None,
    extra_headers: dict | None = None,
) -> list[dict[str, Any]] | dict[str, Any] | None:
    """Direct REST call to Supabase PostgREST API."""
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
    if extra_headers:
        headers.update(extra_headers)

    if body is not None:
        if isinstance(body, list):
            body = [_sanitize_floats(item) if isinstance(item, dict) else item for item in body]
        elif isinstance(body, dict):
            body = _sanitize_floats(body)

    try:
        with httpx.Client(timeout=10) as client:
            if method == "GET":
                r = client.get(endpoint, params=query or {}, headers=headers)
            elif method == "POST":
                # Upsert via POST with resolution=merge-duplicates
                upsert_headers = {**headers, "Prefer": "resolution=merge-duplicates,return=representation"}
                r = client.post(endpoint, json=body, headers=upsert_headers)
            elif method == "PATCH":
                r = client.patch(endpoint, json=body, params=query or {}, headers=headers)
            elif method == "DELETE":
                r = client.delete(endpoint, params=query or {}, headers=headers)
            else:
                return None
            r.raise_for_status()
            return r.json() if r.content else None
    except Exception as e:
        log.warning("Supabase REST call failed for table=%s: %s", table, e)
        return None


def _get_known_columns() -> set[str]:
    global _known_columns
    if _known_columns is not None:
        return _known_columns
    data = _supabase_rest("stock_snapshot", "GET", {"select": "*", "limit": "1"})
    if isinstance(data, list) and data:
        _known_columns = set(data[0].keys())
    else:
        _known_columns = {
            "ticker", "market", "price", "change_pct", "volume", "market_cap",
            "pe_ttm", "eps", "beta", "pb_ratio", "week_52_high", "week_52_low",
            "earnings_date", "analyst_target", "recommendation",
            "rsi_14d", "macd_signal", "insider_score", "news_sentiment",
            "sector", "sub_sector", "company_name", "currency",
            "cached_at", "stale", "source",
        }
    log.info("stock_snapshot columns: %s", sorted(_known_columns))
    return _known_columns


def _reset_known_columns():
    global _known_columns
    _known_columns = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_snapshot(rows: list[dict[str, Any]]) -> int:
    """Batch upsert rows into stock_snapshot keyed on (ticker, market)."""
    if not rows:
        return 0
    known = _get_known_columns()
    now_iso = datetime.now(timezone.utc).isoformat()
    for r in rows:
        r.setdefault("cached_at", now_iso)
    # Filter to only columns that exist in the table
    filtered = [_sanitize_floats({k: v for k, v in r.items() if k in known}) for r in rows]
    result = _supabase_rest("stock_snapshot", method="POST", body=filtered)
    return len(rows) if result is not None else 0


def read_snapshot(ticker: str, market: str) -> dict[str, Any] | None:
    """Read a single stock snapshot by ticker + market."""
    data = _supabase_rest(
        "stock_snapshot",
        method="GET",
        query={
            "select": "*",
            "ticker": f"eq.{ticker.upper()}",
            "market": f"eq.{market}",
            "limit": "1",
        },
    )
    if isinstance(data, list) and data:
        return data[0]
    return None


def read_snapshot_batch(tickers: list[str], market: str) -> list[dict[str, Any]]:
    """Read multiple stock snapshots. Uses PostgREST in=(...) filter."""
    if not tickers:
        return []
    # PostgREST supports in=(A,B,C) for up to ~100 items
    # For larger batches, split into chunks
    CHUNK = 80
    all_results: list[dict] = []
    for i in range(0, len(tickers), CHUNK):
        chunk = tickers[i:i + CHUNK]
        tickers_csv = ",".join(t.upper() for t in chunk)
        data = _supabase_rest(
            "stock_snapshot",
            method="GET",
            query={
                "select": "*",
                "market": f"eq.{market}",
                "ticker": f"in.({tickers_csv})",
            },
        )
        if isinstance(data, list):
            all_results.extend(data)
    return all_results


def read_snapshot_stale(max_age_minutes: int = 35) -> list[dict[str, Any]]:
    """Read all snapshots older than max_age_minutes (default 35 to catch missed 30-min refresh)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)).isoformat()
    data = _supabase_rest(
        "stock_snapshot",
        method="GET",
        query={
            "select": "ticker,market,cached_at",
            "cached_at": f"lt.{cutoff}",
            "limit": "10000",
        },
    )
    return data if isinstance(data, list) else []


def read_all_by_market(market: str, limit: int = 5000) -> list[dict[str, Any]]:
    """Read all snapshots for a market, ordered by change_pct desc."""
    data = _supabase_rest(
        "stock_snapshot",
        method="GET",
        query={
            "select": "*",
            "market": f"eq.{market}",
            "order": "change_pct.desc.nullslast",
            "limit": str(limit),
        },
    )
    return data if isinstance(data, list) else []


def is_stale(row: dict[str, Any], max_age_minutes: int = 35) -> bool:
    """Check if a snapshot row is stale based on cached_at."""
    cached_at = row.get("cached_at")
    if not cached_at:
        return True
    try:
        ts = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - ts
        return age > timedelta(minutes=max_age_minutes)
    except Exception:
        return True


def age_seconds(market: str) -> int | None:
    """Return seconds since newest cached_at for market, or None if empty."""
    data = _supabase_rest(
        "stock_snapshot",
        method="GET",
        query={
            "select": "cached_at",
            "market": f"eq.{market}",
            "order": "cached_at.desc",
            "limit": "1",
        },
    )
    if isinstance(data, list) and data:
        ts = datetime.fromisoformat(data[0]["cached_at"].replace("Z", "+00:00"))
        return int((datetime.now(timezone.utc) - ts).total_seconds())
    return None


def count_by_market(market: str) -> int:
    """Return number of snapshot rows for a market."""
    data = _supabase_rest(
        "stock_snapshot",
        method="GET",
        query={
            "select": "count",
            "market": f"eq.{market}",
        },
    )
    if isinstance(data, list) and data:
        return data[0].get("count", 0)
    return 0

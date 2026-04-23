"""Read/write helpers for public.score_cache.

Populated by scripts/nightly_score.py (nightly GHA).
Read by /screener for sub-100ms responses.
"""
from __future__ import annotations
import os
from datetime import datetime, timezone, timedelta
from typing import Any

from dotenv import load_dotenv
from pathlib import Path
import httpx


_env_loaded = False


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
    except Exception:
        return None


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


def upsert_scores(rows: list[dict[str, Any]]) -> int:
    """Batch upsert rows keyed on (ticker, market). Returns count."""
    if not rows:
        return 0
    now_iso = datetime.now(timezone.utc).isoformat()
    for r in rows:
        r.setdefault("computed_at", now_iso)
    result = _supabase_rest("score_cache", method="POST", body=rows)
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

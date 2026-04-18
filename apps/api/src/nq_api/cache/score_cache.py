"""Read/write helpers for public.score_cache.

Populated by scripts/nightly_score.py (nightly GHA).
Read by /screener for sub-100ms responses.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Any

from nq_api.auth.deps import _supabase_service_client


def read_top(
    market: str,
    n: int = 50,
    max_age_seconds: int = 3600,
) -> list[dict[str, Any]]:
    """Return top-n scored tickers for market if cache fresh, else []."""
    client = _supabase_service_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)).isoformat()
    resp = (
        client.table("score_cache")
        .select("*")
        .eq("market", market)
        .gte("computed_at", cutoff)
        .order("composite_score", desc=True)
        .limit(n)
        .execute()
    )
    return resp.data or []


def upsert_scores(rows: list[dict[str, Any]]) -> int:
    """Batch upsert rows keyed on (ticker, market). Returns count."""
    if not rows:
        return 0
    client = _supabase_service_client()
    now_iso = datetime.now(timezone.utc).isoformat()
    for r in rows:
        r.setdefault("computed_at", now_iso)
    client.table("score_cache").upsert(rows, on_conflict="ticker,market").execute()
    return len(rows)


def age_seconds(market: str) -> int | None:
    """Return seconds since newest computed_at for market, or None if empty."""
    client = _supabase_service_client()
    resp = (
        client.table("score_cache")
        .select("computed_at")
        .eq("market", market)
        .order("computed_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return None
    ts = datetime.fromisoformat(rows[0]["computed_at"].replace("Z", "+00:00"))
    return int((datetime.now(timezone.utc) - ts).total_seconds())

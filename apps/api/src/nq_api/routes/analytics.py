"""Internal analytics dashboard — admin-only growth metrics.

Aggregates user_events and shared_analyses for WAU, viral coefficient,
and top tickers tracking.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from nq_api.auth.deps import get_current_user
from nq_api.auth.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/internal/analytics", tags=["analytics"])


# ── Supabase REST helper ─────────────────────────────────────────────

def _supabase_rest(
    table: str,
    method: str = "GET",
    query: dict | None = None,
    body: list[dict] | dict | None = None,
) -> list[dict] | dict | None:
    """Direct REST call to Supabase PostgREST."""
    import os
    import httpx

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

    # Sanitize body before JSON serialization (NaN/Inf → None, Supabase rejects NaN)
    if body is not None:
        from nq_api.cache.score_cache import _sanitize_floats
        if isinstance(body, list):
            body = [_sanitize_floats(item) if isinstance(item, dict) else item for item in body]
        elif isinstance(body, dict):
            body = _sanitize_floats(body)

    try:
        with httpx.Client(timeout=15) as client:
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
    except Exception as exc:
        logger.warning("Analytics REST %s %s failed: %s", method, table, exc)
        return None


# ── Admin check ───────────────────────────────────────────────────────

def _admin_emails() -> set[str]:
    raw = os.environ.get("ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def _require_admin(user: User) -> None:
    """True admin gate — an allowlist of emails (ADMIN_EMAILS env), NOT the
    subscription tier. A paying pro/api customer is not an admin and must not
    see platform-wide growth metrics or other users' ids."""
    admins = _admin_emails()
    if not admins or (user.email or "").strip().lower() not in admins:
        raise HTTPException(status_code=403, detail="Admin access required")


# ── Endpoint ───────────────────────────────────────────────────────────

@router.get("/dashboard")
async def analytics_dashboard(
    period: str = Query("7d", pattern="^(24h|7d|30d)$"),
    user: User = Depends(get_current_user),
):
    """Admin-only analytics dashboard. Returns growth metrics."""
    _require_admin(user)

    now = datetime.now(timezone.utc)
    if period == "24h":
        since = now - timedelta(hours=24)
    elif period == "30d":
        since = now - timedelta(days=30)
    else:
        since = now - timedelta(days=7)

    since_iso = since.isoformat()

    # ── Fetch events ──────────────────────────────────────────────
    events = _supabase_rest(
        "user_events",
        "GET",
        query={
            "select": "id,event_type,category,label,payload,created_at,user_id",
            "created_at": f"gte.{since_iso}",
            "order": "created_at.desc",
            "limit": "10000",
        },
    ) or []

    # ── Fetch shared analyses ─────────────────────────────────────
    shares = _supabase_rest(
        "shared_analyses",
        "GET",
        query={
            "select": "share_id,ticker,market,verdict,score,view_count,created_at,creator_id",
            "created_at": f"gte.{since_iso}",
            "order": "created_at.desc",
            "limit": "5000",
        },
    ) or []

    # ── Aggregate ─────────────────────────────────────────────────
    events_by_type: dict[str, int] = {}
    unique_users: set[str] = set()
    daily: dict[str, dict] = {}

    for ev in events:
        et = ev.get("event_type", "unknown")
        events_by_type[et] = events_by_type.get(et, 0) + 1
        uid = ev.get("user_id")
        if uid:
            unique_users.add(uid)
        # Daily bucket
        day = (ev.get("created_at") or "")[:10]
        if day:
            bucket = daily.setdefault(day, {"events": 0, "shares": 0, "views": 0})
            bucket["events"] += 1

    # ── Shares aggregation ────────────────────────────────────────
    total_shares_created = len(shares)
    total_share_views = sum(s.get("view_count", 0) for s in shares)
    ticker_counts: dict[str, dict] = {}

    for s in shares:
        t = s.get("ticker", "UNKNOWN")
        if t not in ticker_counts:
            ticker_counts[t] = {"shares": 0, "views": 0}
        ticker_counts[t]["shares"] += 1
        ticker_counts[t]["views"] += s.get("view_count", 0)
        # Mark shares in daily
        day = (s.get("created_at") or "")[:10]
        if day and day in daily:
            daily[day]["shares"] += 1

    # Sort tickers by shares descending
    top_tickers = sorted(
        [{"ticker": k, **v} for k, v in ticker_counts.items()],
        key=lambda x: x["shares"],
        reverse=True,
    )[:20]

    # Sort daily by date
    daily_breakdown = sorted(
        [{"date": k, **v} for k, v in daily.items()],
        key=lambda x: x["date"],
    )

    # ── Conversion funnel ─────────────────────────────────────────
    shares_created_count = events_by_type.get("analysis_shared", 0)
    shares_viewed_count = events_by_type.get("analysis_viewed", 0)
    signups_from_share = events_by_type.get("signup_from_share", 0)

    return {
        "period": period,
        "summary": {
            "total_events": len(events),
            "total_shares_created": total_shares_created,
            "total_share_views": total_share_views,
            "unique_active_users": len(unique_users),
        },
        "events_by_type": events_by_type,
        "top_shared_tickers": top_tickers,
        "daily_breakdown": daily_breakdown,
        "conversion_funnel": {
            "shares_created": shares_created_count,
            "shares_viewed": shares_viewed_count,
            "signups_from_share": signups_from_share,
        },
    }
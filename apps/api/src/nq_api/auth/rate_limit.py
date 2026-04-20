"""Per-tier daily rate limiting via public.usage_log.

enforce_tier_quota(endpoint) -> FastAPI dep that:
  1. Requires authed user (get_current_user).
  2. Counts today's usage_log rows for (user, endpoint).
  3. Compares against TIER_LIMITS[tier].queries_per_day
     (or .backtest_per_day when endpoint == "backtest").
  4. Inserts usage_log row on pass; raises 429 on cap.
"""
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status

from .deps import get_current_user, _supabase_service_client
from .models import User, TIER_LIMITS


def _cap_for(tier: str, endpoint: str) -> int:
    lim = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    if endpoint == "backtest":
        return lim.backtest_per_day
    return lim.queries_per_day


def _today_count(user_id: str, endpoint: str) -> int:
    client = _supabase_service_client()
    today = datetime.now(timezone.utc).date().isoformat()
    resp = (
        client.table("usage_log")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("endpoint", endpoint)
        .gte("ts", f"{today}T00:00:00Z")
        .execute()
    )
    return resp.count or 0


def _record(user_id: str, endpoint: str) -> None:
    client = _supabase_service_client()
    client.table("usage_log").insert(
        {"user_id": user_id, "endpoint": endpoint}
    ).execute()


def enforce_tier_quota(endpoint: str):
    """Return a dep that enforces the daily cap on `endpoint` for the user."""

    def _dep(user: User = Depends(get_current_user)) -> User:
        cap = _cap_for(user.tier, endpoint)
        if cap == 0:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"{endpoint} not available on {user.tier} tier — upgrade required",
            )
        used = _today_count(user.id, endpoint)
        if used >= cap:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"daily cap reached ({used}/{cap}) on {user.tier} tier — upgrade or retry tomorrow",
            )
        _record(user.id, endpoint)
        return user

    return _dep

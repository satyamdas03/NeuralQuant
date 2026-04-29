"""Per-tier daily rate limiting via public.usage_log.

enforce_tier_quota(endpoint) -> FastAPI dep that:
  1. Requires authed user (get_current_user).
  2. Counts today's usage_log rows for (user, endpoint) via direct httpx REST.
  3. Compares against TIER_LIMITS[tier].queries_per_day
     (or .backtest_per_day when endpoint == "backtest").
  4. Inserts usage_log row on pass; raises 429 on cap.

Uses direct httpx REST to PostgREST — avoids RemoteProtocolError from
supabase Python SDK in uvicorn's asyncio context.
"""
from __future__ import annotations
import logging
import os
from datetime import datetime, timezone

import httpx
from fastapi import Depends, HTTPException, status

from .deps import get_current_user
from .models import User, TIER_LIMITS

log = logging.getLogger(__name__)


def _usage_rest(
    method: str,
    query: dict[str, str] | None = None,
    body: dict | None = None,
) -> dict | list | None:
    """Direct httpx REST to PostgREST usage_log table."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required")
    endpoint = f"{url}/rest/v1/usage_log"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation,count=exact",
    }
    try:
        with httpx.Client(timeout=10) as c:
            if method == "GET":
                r = c.get(endpoint, params=query or {}, headers=headers)
            elif method == "POST":
                r = c.post(endpoint, json=body or {}, headers=headers)
            else:
                raise ValueError(f"unsupported method {method}")
            r.raise_for_status()
            return {"data": r.json() if r.content else [], "headers": dict(r.headers)}
    except httpx.HTTPStatusError as exc:
        log.warning("usage_log %s -> %s: %s", method, exc.response.status_code, exc.response.text[:200])
        raise
    except Exception as exc:
        log.exception("usage_log %s failed", method)
        raise


def _cap_for(tier: str, endpoint: str) -> int:
    lim = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    if endpoint == "backtest":
        return lim.backtest_per_day
    return lim.queries_per_day


def _today_count(user_id: str, endpoint: str) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    resp = _usage_rest(
        "GET",
        query={
            "select": "id",
            "user_id": f"eq.{user_id}",
            "endpoint": f"eq.{endpoint}",
            "ts": f"gte.{today}T00:00:00Z",
        },
    )
    content_range = (resp or {}).get("headers", {}).get("content-range", "0/0")
    try:
        return int(content_range.split("/")[-1])
    except (ValueError, IndexError):
        return len((resp or {}).get("data", []))


def _record(user_id: str, endpoint: str) -> None:
    _usage_rest("POST", body={"user_id": user_id, "endpoint": endpoint})


def enforce_tier_quota(endpoint: str):
    """Return a dep that enforces the daily cap on `endpoint` for the user."""

    def _dep(user: User = Depends(get_current_user)) -> User:
        # Dev-mode bypass: skip tier gates entirely in development
        if os.environ.get("ENVIRONMENT") == "development":
            return user
        cap = _cap_for(user.tier, endpoint) + user.referral_bonus_queries
        if cap == 0:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"{endpoint} not available on {user.tier} tier — upgrade required",
            )
        try:
            used = _today_count(user.id, endpoint)
        except Exception as exc:
            log.exception("rate_limit _today_count failed")
            raise HTTPException(500, f"quota check failed: {exc}") from exc
        if used >= cap:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"daily cap reached ({used}/{cap}) on {user.tier} tier — upgrade or retry tomorrow",
            )
        try:
            _record(user.id, endpoint)
        except Exception as exc:
            log.exception("rate_limit _record failed")
            raise HTTPException(500, f"usage log insert failed: {exc}") from exc
        return user

    return _dep
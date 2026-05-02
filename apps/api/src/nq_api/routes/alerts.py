"""Alert CRUD + delivery log — Supabase-backed, RLS-enforced.

Uses direct httpx REST to PostgREST (see `cache/score_cache.py`) because the
`supabase` Python SDK's `postgrest` transport produces
`httpx.RemoteProtocolError: illegal request line` inside uvicorn's asyncio
context. Every previous SDK-based call here was returning HTTP 500.
"""
from __future__ import annotations
import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from nq_api.auth import User, get_current_user
from nq_api.schemas_alerts import (
logger = logging.getLogger(__name__)
    AlertSubscriptionCreate,
    AlertSubscription,
    AlertSubscriptionListResponse,
    AlertDelivery,
    AlertDeliveryListResponse,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])
log = logging.getLogger(__name__)

ALERT_LIMITS = {"free": 5, "investor": 25, "pro": 100, "api": 1000}


def _rest(
    table: str,
    method: str = "GET",
    query: dict[str, str] | None = None,
    body: Any = None,
    extra_headers: dict[str, str] | None = None,
) -> Any:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    endpoint = f"{url}/rest/v1/{table}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    if extra_headers:
        headers.update(extra_headers)
    try:
        with httpx.Client(timeout=10) as c:
            if method == "GET":
                r = c.get(endpoint, params=query or {}, headers=headers)
            elif method == "POST":
                r = c.post(endpoint, params=query or {}, json=body, headers=headers)
            elif method == "DELETE":
                r = c.delete(endpoint, params=query or {}, headers=headers)
            else:
                raise HTTPException(status_code=500, detail=f"bad method {method}")
            r.raise_for_status()
            # PostgREST returns headers; we may need count from Content-Range
            return {
                "data": r.json() if r.content else [],
                "headers": dict(r.headers),
            }
    except httpx.HTTPStatusError as exc:
        log.warning("PostgREST %s %s -> %s: %s", method, table, exc.response.status_code, exc.response.text[:200])
        raise HTTPException(status_code=502, detail=f"Supabase error: {exc.response.status_code}")
    except Exception as exc:
        log.exception("PostgREST %s %s failed", method, table)
        raise HTTPException(status_code=502, detail=f"Supabase request failed: {exc}")


@router.get("/subscriptions", response_model=AlertSubscriptionListResponse)
def list_subscriptions(user: User = Depends(get_current_user)) -> AlertSubscriptionListResponse:
    resp = _rest(
        "alert_subscriptions",
        method="GET",
        query={
            "select": "*",
            "user_id": f"eq.{user.id}",
            "order": "created_at.desc",
        },
    )
    rows = resp["data"] or []
    items = [AlertSubscription(**r) for r in rows]
    return AlertSubscriptionListResponse(items=items, count=len(items))


@router.post("/subscriptions", response_model=AlertSubscription, status_code=201)
def create_subscription(
    req: AlertSubscriptionCreate, user: User = Depends(get_current_user)
) -> AlertSubscription:
    limit = ALERT_LIMITS.get(user.tier, 5)

    # Quota count via Prefer: count=exact
    count_resp = _rest(
        "alert_subscriptions",
        method="GET",
        query={
            "select": "id",
            "user_id": f"eq.{user.id}",
        },
        extra_headers={"Prefer": "count=exact"},
    )
    content_range = count_resp["headers"].get("content-range", "0/0")
    try:
        current = int(content_range.split("/")[-1])
    except Exception as e:
        logger.debug("Non-critical enrichment failed: %s", e)
        current = len(count_resp["data"] or [])
    if current >= limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"alert limit reached ({limit} for tier={user.tier})",
        )

    ticker = req.ticker.upper().strip()
    insert_body = [{
        "user_id": user.id,
        "ticker": ticker,
        "market": req.market,
        "alert_type": req.alert_type,
        "threshold": req.threshold,
        "min_delta": req.min_delta,
    }]
    resp = _rest("alert_subscriptions", method="POST", body=insert_body)
    rows = resp["data"] or []
    if not rows:
        raise HTTPException(status_code=409, detail="subscription already exists")
    return AlertSubscription(**rows[0])


@router.delete("/subscriptions/{sub_id}", status_code=204)
def delete_subscription(sub_id: str, user: User = Depends(get_current_user)) -> None:
    resp = _rest(
        "alert_subscriptions",
        method="DELETE",
        query={
            "id": f"eq.{sub_id}",
            "user_id": f"eq.{user.id}",
        },
    )
    if not (resp["data"] or []):
        raise HTTPException(status_code=404, detail="not found")
    return None


@router.get("/deliveries", response_model=AlertDeliveryListResponse)
def list_deliveries(
    limit: int = 20, user: User = Depends(get_current_user)
) -> AlertDeliveryListResponse:
    resp = _rest(
        "alert_deliveries",
        method="GET",
        query={
            "select": "*",
            "user_id": f"eq.{user.id}",
            "order": "delivered_at.desc",
            "limit": str(min(limit, 100)),
        },
    )
    rows = resp["data"] or []
    items = [AlertDelivery(**r) for r in rows]
    return AlertDeliveryListResponse(items=items, count=len(items))

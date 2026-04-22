"""Alert CRUD + delivery log — Supabase-backed, RLS-enforced."""
from __future__ import annotations
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from nq_api.auth import User, get_current_user
from nq_api.auth.models import TIER_LIMITS
from nq_api.schemas_alerts import (
    AlertSubscriptionCreate,
    AlertSubscription,
    AlertSubscriptionListResponse,
    AlertDelivery,
    AlertDeliveryListResponse,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _client():
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


ALERT_LIMITS = {"free": 5, "investor": 25, "pro": 100, "api": 1000}


@router.get("/subscriptions", response_model=AlertSubscriptionListResponse)
def list_subscriptions(user: User = Depends(get_current_user)) -> AlertSubscriptionListResponse:
    resp = (
        _client()
        .table("alert_subscriptions")
        .select("*")
        .eq("user_id", user.id)
        .order("created_at", desc=True)
        .execute()
    )
    rows = resp.data or []
    items = [AlertSubscription(**r) for r in rows]
    return AlertSubscriptionListResponse(items=items, count=len(items))


@router.post("/subscriptions", response_model=AlertSubscription, status_code=201)
def create_subscription(
    req: AlertSubscriptionCreate, user: User = Depends(get_current_user)
) -> AlertSubscription:
    limit = ALERT_LIMITS.get(user.tier, 5)
    client = _client()

    count_resp = (
        client.table("alert_subscriptions")
        .select("id", count="exact")
        .eq("user_id", user.id)
        .execute()
    )
    current = count_resp.count or 0
    if current >= limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"alert limit reached ({limit} for tier={user.tier})",
        )

    ticker = req.ticker.upper().strip()
    insert = (
        client.table("alert_subscriptions")
        .insert({
            "user_id": user.id,
            "ticker": ticker,
            "market": req.market,
            "alert_type": req.alert_type,
            "threshold": req.threshold,
            "min_delta": req.min_delta,
        })
        .execute()
    )
    rows = insert.data or []
    if not rows:
        raise HTTPException(status_code=409, detail="subscription already exists")
    return AlertSubscription(**rows[0])


@router.delete("/subscriptions/{sub_id}", status_code=204)
def delete_subscription(sub_id: str, user: User = Depends(get_current_user)) -> None:
    resp = (
        _client()
        .table("alert_subscriptions")
        .delete()
        .eq("id", sub_id)
        .eq("user_id", user.id)
        .execute()
    )
    if not (resp.data or []):
        raise HTTPException(status_code=404, detail="not found")
    return None


@router.get("/deliveries", response_model=AlertDeliveryListResponse)
def list_deliveries(
    limit: int = 20, user: User = Depends(get_current_user)
) -> AlertDeliveryListResponse:
    resp = (
        _client()
        .table("alert_deliveries")
        .select("*")
        .eq("user_id", user.id)
        .order("delivered_at", desc=True)
        .limit(min(limit, 100))
        .execute()
    )
    rows = resp.data or []
    items = [AlertDelivery(**r) for r in rows]
    return AlertDeliveryListResponse(items=items, count=len(items))
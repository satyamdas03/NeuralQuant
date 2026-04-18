"""Watchlist CRUD — per-user, Supabase-backed, RLS-enforced via JWT."""
from __future__ import annotations
import os
from fastapi import APIRouter, Depends, HTTPException, status

from nq_api.auth import User, get_current_user
from nq_api.auth.models import TIER_LIMITS
from nq_api.schemas_watchlist import (
    WatchlistItem,
    WatchlistAddRequest,
    WatchlistListResponse,
)

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


def _client():
    from supabase import create_client  # type: ignore
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


@router.get("", response_model=WatchlistListResponse)
def list_watchlist(user: User = Depends(get_current_user)) -> WatchlistListResponse:
    resp = (
        _client()
        .table("watchlists")
        .select("*")
        .eq("user_id", user.id)
        .order("created_at", desc=True)
        .execute()
    )
    rows = resp.data or []
    items = [WatchlistItem(**r) for r in rows]
    return WatchlistListResponse(items=items, count=len(items))


@router.post("", response_model=WatchlistItem, status_code=201)
def add_watchlist(
    req: WatchlistAddRequest, user: User = Depends(get_current_user)
) -> WatchlistItem:
    limit = TIER_LIMITS[user.tier].watchlist_max
    client = _client()

    count_resp = (
        client.table("watchlists")
        .select("id", count="exact")
        .eq("user_id", user.id)
        .execute()
    )
    current = count_resp.count or 0
    if current >= limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"watchlist limit reached ({limit} for tier={user.tier})",
        )

    ticker = req.ticker.upper().strip()
    insert = (
        client.table("watchlists")
        .insert(
            {
                "user_id": user.id,
                "ticker": ticker,
                "market": req.market,
                "note": req.note,
            }
        )
        .execute()
    )
    rows = insert.data or []
    if not rows:
        raise HTTPException(status_code=409, detail="already in watchlist")
    return WatchlistItem(**rows[0])


@router.delete("/{item_id}", status_code=204)
def delete_watchlist(
    item_id: str, user: User = Depends(get_current_user)
) -> None:
    resp = (
        _client()
        .table("watchlists")
        .delete()
        .eq("id", item_id)
        .eq("user_id", user.id)
        .execute()
    )
    if not (resp.data or []):
        raise HTTPException(status_code=404, detail="not found")
    return None

"""Watchlist CRUD — per-user, Supabase-backed, RLS-enforced via JWT.

Uses direct httpx REST to PostgREST to avoid `httpx.RemoteProtocolError`
failures that the `supabase` Python SDK produces inside uvicorn's asyncio
context (see `cache/score_cache.py` and `routes/alerts.py`).
"""
from __future__ import annotations
import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from nq_api.auth import User, get_current_user
from nq_api.auth.models import TIER_LIMITS
from nq_api.schemas_watchlist import (
    WatchlistItem,
    WatchlistAddRequest,
    WatchlistListResponse,
)

router = APIRouter(prefix="/watchlist", tags=["watchlist"])
log = logging.getLogger(__name__)


def _rest(
    method: str,
    query: dict[str, str] | None = None,
    body: Any = None,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    endpoint = f"{url}/rest/v1/watchlists"
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
            return {
                "data": r.json() if r.content else [],
                "headers": dict(r.headers),
            }
    except httpx.HTTPStatusError as exc:
        log.warning("watchlists %s -> %s: %s", method, exc.response.status_code, exc.response.text[:200])
        # 409 on unique constraint (user_id, ticker, market) — surface as 409
        if exc.response.status_code == 409:
            raise HTTPException(status_code=409, detail="already in watchlist")
        raise HTTPException(status_code=502, detail=f"Supabase error: {exc.response.status_code}")
    except Exception as exc:
        log.exception("watchlists %s failed", method)
        raise HTTPException(status_code=502, detail=f"Supabase request failed: {exc}")


@router.get("", response_model=WatchlistListResponse)
def list_watchlist(user: User = Depends(get_current_user)) -> WatchlistListResponse:
    resp = _rest(
        "GET",
        query={
            "select": "*",
            "user_id": f"eq.{user.id}",
            "order": "created_at.desc",
        },
    )
    rows = resp["data"] or []
    items = [WatchlistItem(**r) for r in rows]
    return WatchlistListResponse(items=items, count=len(items))


@router.post("", response_model=WatchlistItem, status_code=201)
def add_watchlist(
    req: WatchlistAddRequest, user: User = Depends(get_current_user)
) -> WatchlistItem:
    limit = TIER_LIMITS[user.tier].watchlist_max

    count_resp = _rest(
        "GET",
        query={
            "select": "id",
            "user_id": f"eq.{user.id}",
        },
        extra_headers={"Prefer": "count=exact"},
    )
    content_range = count_resp["headers"].get("content-range", "0/0")
    try:
        current = int(content_range.split("/")[-1])
    except Exception:
        current = len(count_resp["data"] or [])

    if current >= limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"watchlist limit reached ({limit} for tier={user.tier})",
        )

    ticker = req.ticker.upper().strip()
    insert_body = [{
        "user_id": user.id,
        "ticker": ticker,
        "market": req.market,
        "note": req.note,
    }]
    resp = _rest("POST", body=insert_body)
    rows = resp["data"] or []
    if not rows:
        raise HTTPException(status_code=409, detail="already in watchlist")
    return WatchlistItem(**rows[0])


@router.delete("/{item_id}", status_code=204)
def delete_watchlist(
    item_id: str, user: User = Depends(get_current_user)
) -> None:
    resp = _rest(
        "DELETE",
        query={
            "id": f"eq.{item_id}",
            "user_id": f"eq.{user.id}",
        },
    )
    if not (resp["data"] or []):
        raise HTTPException(status_code=404, detail="not found")
    return None

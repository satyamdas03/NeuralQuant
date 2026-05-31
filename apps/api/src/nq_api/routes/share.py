"""Shareable PARA-DEBATE analysis pages — viral growth loop.

Public endpoints: create share links, view shared analyses, dynamic OG images.
Auth-optional: guests can share and view. Delete requires creator auth.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from nq_api.auth.deps import get_current_user, get_current_user_optional
from nq_api.auth.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/share", tags=["share"])


# ── Helpers ─────────────────────────────────────────────────────────

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

    try:
        with httpx.Client(timeout=10) as client:
            if method == "GET":
                r = client.get(endpoint, params=query or {}, headers=headers)
            elif method == "POST":
                r = client.post(endpoint, json=body, headers=headers)
            elif method == "PATCH":
                r = client.patch(endpoint, json=body, params=query or {}, headers=headers)
            elif method == "DELETE":
                r = client.delete(endpoint, params=query or {}, headers=headers)
            else:
                return None
            r.raise_for_status()
            return r.json() if r.content else None
    except Exception as exc:
        logger.warning("Share REST %s %s failed: %s", method, table, exc)
        return None


def _fire_event(event_type: str, label: str | None = None, payload: dict | None = None,
                user_id: str | None = None, session_id: str | None = None) -> None:
    """Best-effort fire-and-forget event write to user_events."""
    row = {
        "event_type": event_type,
        "category": "share",
        "label": label,
        "payload": payload or {},
        "user_id": user_id,
        "session_id": session_id,
    }
    try:
        _supabase_rest("user_events", "POST", body=[row])
    except Exception:
        pass  # Non-blocking — never fail a request for analytics


# ── Schemas ───────────────────────────────────────────────────────────

VALID_VERDICTS = {"STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL", "BULL", "BEAR", "NEUTRAL"}


class ShareAnalysisRequest(BaseModel):
    model_config = {"extra": "allow"}  # Accept unknown fields gracefully

    ticker: str = Field(..., min_length=1, max_length=20)
    market: str = Field("US", pattern="^(US|IN)$")
    analyst_response: dict = Field(default_factory=dict)
    score_data: dict | None = None
    meta_data: dict | None = None
    sentiment_data: dict | None = None
    verdict: str = Field("HOLD")
    score: float | None = Field(None)


class ShareAnalysisResponse(BaseModel):
    share_id: str
    url: str


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post("/analysis", response_model=ShareAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_share(
    req: ShareAnalysisRequest,
    user: User | None = Depends(get_current_user_optional),
):
    """Create a shareable link for a PARA-DEBATE analysis. No auth required."""
    logger.info("[share] create_share: ticker=%s market=%s verdict=%s score=%s user=%s",
                req.ticker, req.market, req.verdict, req.score,
                user.id if user else "guest")
    share_id = secrets.token_urlsafe(12)

    # Normalize verdict
    verdict = req.verdict.upper().replace(" ", "_")
    if verdict not in VALID_VERDICTS:
        verdict = "HOLD"

    row = {
        "share_id": share_id,
        "ticker": req.ticker.upper(),
        "market": req.market,
        "analyst_response": req.analyst_response,
        "score_data": req.score_data or {},
        "meta_data": req.meta_data or {},
        "sentiment_data": req.sentiment_data or {},
        "verdict": verdict,
        "score": req.score if req.score is not None else 5.0,
        "creator_id": str(user.id) if user else None,
        "creator_email": user.email if user else None,
        "is_public": True,
    }

    result = _supabase_rest("shared_analyses", "POST", body=[row])
    if not result:
        raise HTTPException(status_code=502, detail="Failed to create share link")

    _fire_event(
        "analysis_shared",
        label=f"{req.ticker}:{verdict}",
        payload={"share_id": share_id, "ticker": req.ticker, "market": req.market, "verdict": verdict, "score": req.score},
        user_id=str(user.id) if user else None,
    )

    base_url = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://neuralquant.co").rstrip("/")
    url = f"{base_url}/analysis/{share_id}"
    return ShareAnalysisResponse(share_id=share_id, url=url)


@router.get("/analysis/{share_id}")
async def get_share(share_id: str):
    """Public: view a shared analysis. Increments view_count."""
    rows = _supabase_rest(
        "shared_analyses",
        "GET",
        query={"share_id": f"eq.{share_id}", "is_public": "eq.true", "select": "*"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Analysis not found")

    row = rows[0] if isinstance(rows, list) else rows

    # Best-effort view count increment
    try:
        _supabase_rest(
            "shared_analyses",
            "PATCH",
            query={"share_id": f"eq.{share_id}"},
            body={"view_count": (row.get("view_count") or 0) + 1},
        )
    except Exception:
        pass  # Non-critical

    _fire_event(
        "analysis_viewed",
        label=f"{row.get('ticker')}:{row.get('verdict')}",
        payload={"share_id": share_id, "ticker": row.get("ticker"), "market": row.get("market")},
    )

    return row


@router.delete("/analysis/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_share(share_id: str, user: User = Depends(get_current_user)):
    """Auth required: delete a share. Only the creator can delete."""
    rows = _supabase_rest(
        "shared_analyses",
        "GET",
        query={"share_id": f"eq.{share_id}", "select": "creator_id"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Analysis not found")

    row = rows[0] if isinstance(rows, list) else rows
    if row.get("creator_id") != str(user.id):
        raise HTTPException(status_code=403, detail="Only the creator can delete this analysis")

    _supabase_rest("shared_analyses", "DELETE", query={"share_id": f"eq.{share_id}"})
    return None


# Make os available at module level (used in create_share)
import os
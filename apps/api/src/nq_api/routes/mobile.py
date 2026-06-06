"""Mobile push token management for Expo notifications."""
from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from nq_api.auth.deps import get_current_user
from nq_api.auth.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mobile", tags=["mobile"])


class PushTokenRequest(BaseModel):
    token: str
    platform: str  # "ios" or "android"


def _supabase_rest(
    table: str,
    method: str = "GET",
    query: dict | None = None,
    body: list[dict] | dict | None = None,
) -> list[dict] | dict | None:
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
            elif method == "DELETE":
                r = client.delete(endpoint, params=query or {}, headers=headers)
            else:
                return None
            r.raise_for_status()
            return r.json() if r.content else None
    except Exception as exc:
        logger.warning("Mobile REST %s %s failed: %s", method, table, exc)
        return None


@router.post("/push-token")
async def register_push_token(
    req: PushTokenRequest,
    user: User = Depends(get_current_user),
):
    """Register or update Expo push token for mobile notifications."""
    if req.platform not in ("ios", "android"):
        raise HTTPException(status_code=400, detail="platform must be 'ios' or 'android'")

    # Upsert: delete existing for this user+platform, then insert
    _supabase_rest(
        "mobile_push_tokens",
        "DELETE",
        query={
            "user_id": f"eq.{user.id}",
            "platform": f"eq.{req.platform}",
        },
    )

    result = _supabase_rest(
        "mobile_push_tokens",
        "POST",
        body={
            "user_id": user.id,
            "token": req.token,
            "platform": req.platform,
        },
    )

    if result is None:
        raise HTTPException(status_code=500, detail="Failed to register push token")

    return {"status": "registered", "platform": req.platform}


@router.delete("/push-token")
async def delete_push_token(
    platform: str,
    user: User = Depends(get_current_user),
):
    """Remove push token (e.g., on logout)."""
    if platform not in ("ios", "android"):
        raise HTTPException(status_code=400, detail="platform must be 'ios' or 'android'")

    _supabase_rest(
        "mobile_push_tokens",
        "DELETE",
        query={
            "user_id": f"eq.{user.id}",
            "platform": f"eq.{platform}",
        },
    )

    return {"status": "deleted", "platform": platform}
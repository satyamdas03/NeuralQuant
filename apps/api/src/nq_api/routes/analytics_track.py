"""
Analytics event tracking route.
Receives events from the frontend and stores in user_events table.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from nq_api.services.supabase_helpers import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/track")
async def track_event(request: Request):
    """
    Track an analytics event.
    No auth required — events can be anonymous.
    Stores in user_events table.
    """
    try:
        body = await request.json()
        event_type = body.get("event_type", "unknown")
        properties = body.get("properties", {})

        # Get user ID from auth header if available
        user_id = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                # Lightweight user extraction — don't block on auth failure
                from nq_api.routes.auth import _get_user
                user = await _get_user(auth_header.replace("Bearer ", ""))
                user_id = user.id if user else None
            except Exception:
                pass

        # Get session ID from cookie or header
        session_id = request.headers.get("x-session-id")

        # Store in user_events
        supabase = get_supabase()
        supabase.table("user_events").insert({
            "user_id": user_id,
            "session_id": session_id,
            "event_type": event_type,
            "category": properties.pop("category", "general"),
            "label": properties.pop("label", None),
            "payload": properties,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()

        return {"status": "ok"}

    except Exception as e:
        # Never return errors for analytics — silent fail
        logger.debug(f"Analytics track failed: {e}")
        return {"status": "ok"}

"""
Analytics event tracking route.
Receives events from the frontend and stores in user_events table.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request

from nq_api.cache.score_cache import _supabase_rest

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
                from nq_api.auth.deps import get_current_user_optional
                user = await get_current_user_optional(request)
                user_id = str(user.id) if user else None
            except Exception:
                pass

        # Get session ID from cookie or header
        session_id = request.headers.get("x-session-id")

        # Extract category and label from properties
        category = properties.pop("category", "general") if isinstance(properties, dict) else "general"
        label = properties.pop("label", None) if isinstance(properties, dict) else None

        # Store in user_events via Supabase REST (silent-fail)
        _supabase_rest(
            "user_events",
            "POST",
            body=[{
                "user_id": user_id,
                "session_id": session_id,
                "event_type": event_type,
                "category": category,
                "label": label,
                "payload": properties if isinstance(properties, dict) else {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }],
        )

        return {"status": "ok"}

    except Exception as e:
        # Never return errors for analytics — silent fail
        logger.debug(f"Analytics track failed: {e}")
        return {"status": "ok"}
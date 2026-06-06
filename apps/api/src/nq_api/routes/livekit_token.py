"""POST /livekit/token — generate LiveKit access token for QuantAstra calls."""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends
from livekit.api import (
    AccessToken,
    CreateAgentDispatchRequest,
    LiveKitAPI,
    RoomAgentDispatch,
    VideoGrants,
)

from nq_api.auth.deps import get_current_user_optional

log = logging.getLogger(__name__)

router = APIRouter()

LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "")
LIVEKIT_KEY = os.environ.get("LIVEKIT_API_KEY", "")
LIVEKIT_SECRET = os.environ.get("LIVEKIT_API_SECRET", "")

# Use https:// URL for REST API calls (wss:// is WebSocket only)
LIVEKIT_API_URL = LIVEKIT_URL.replace("wss://", "https://") if LIVEKIT_URL else ""


@router.post("/livekit/token")
async def generate_token(user=Depends(get_current_user_optional)):
    """Generate a LiveKit access token for the QuantAstra agent room.

    Authenticated users get a room scoped to their user ID.
    Guests get an anonymous room with a random UUID.

    Also dispatches the quantastra agent worker to the room via
    LiveKit AgentDispatch API so the agent joins automatically.
    """
    user_id = user.id if user else f"anonymous-{uuid.uuid4().hex[:8]}"
    room = f"quantastra-{user_id}"

    # Track Astra session start
    try:
        from nq_api.routes.analytics_track import router as _ar
        from nq_api.cache.score_cache import _supabase_rest
        from datetime import datetime, timezone
        _supabase_rest(
            "user_events",
            "POST",
            body=[{
                "user_id": str(user.id) if user else None,
                "session_id": room,
                "event_type": "astra_session",
                "category": "voice",
                "label": "session_start",
                "payload": {"room": room, "authenticated": bool(user)},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }],
        )
    except Exception:
        log.debug("Astra session analytics failed (non-critical)")

    if not LIVEKIT_KEY or not LIVEKIT_SECRET:
        return {
            "status": "unavailable",
            "message": "LiveKit is not configured on the server",
        }

    token = (
        AccessToken(LIVEKIT_KEY, LIVEKIT_SECRET)
        .with_identity(user_id)
        .with_name(user.email if user and hasattr(user, "email") else "Guest")
        .with_grants(VideoGrants(room_join=True, room=room))
        .to_jwt()
    )

    # Dispatch the quantastra agent worker to the room.
    # Without this, the worker registers but never receives room events.
    try:
        lk_api = LiveKitAPI(
            url=LIVEKIT_API_URL,
            api_key=LIVEKIT_KEY,
            api_secret=LIVEKIT_SECRET,
        )
        dispatch_req = CreateAgentDispatchRequest(
            agent_name="quantastra",
            room=room,
            metadata="",
        )
        dispatch = await lk_api.agent_dispatch.create_dispatch(dispatch_req)
        log.info(
            "Agent dispatch created: room=%s dispatch_id=%s state=%s",
            room,
            dispatch.id if hasattr(dispatch, "id") else "unknown",
            dispatch.state if hasattr(dispatch, "state") else "unknown",
        )
        await lk_api.aclose()
    except Exception:
        log.exception("Failed to create agent dispatch for room=%s", room)
        # Don't fail the request — user can still connect, agent may join
        # via retry or the 15s frontend timeout will show a message

    return {
        "token": token,
        "url": LIVEKIT_URL,
        "room": room,
    }

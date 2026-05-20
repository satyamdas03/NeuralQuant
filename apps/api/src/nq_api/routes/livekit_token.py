"""POST /livekit/token — generate LiveKit access token for QuantAstra calls."""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends
from livekit.api import AccessToken, VideoGrants

from nq_api.auth.deps import get_current_user_optional

log = logging.getLogger(__name__)

router = APIRouter()

LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "")
LIVEKIT_KEY = os.environ.get("LIVEKIT_API_KEY", "")
LIVEKIT_SECRET = os.environ.get("LIVEKIT_API_SECRET", "")


@router.post("/livekit/token")
async def generate_token(user=Depends(get_current_user_optional)):
    """Generate a LiveKit access token for the QuantAstra agent room.

    Authenticated users get a room scoped to their user ID.
    Guests get an anonymous room with a random UUID.
    """
    user_id = user.id if user else f"anonymous-{uuid.uuid4().hex[:8]}"
    room = f"quantastra-{user_id}"

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

    return {
        "token": token,
        "url": LIVEKIT_URL,
        "room": room,
    }

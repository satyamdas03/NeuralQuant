"""POST /livekit/token — LiveKit access tokens for QuantAstra and Veronica."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from livekit.api import (
    AccessToken,
    CreateAgentDispatchRequest,
    LiveKitAPI,
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

VERONICA_DAILY_CAP_S = 1800  # 30 min/day fuse
ORPHAN_SESSION_S = 600       # session_start without session_end (tab killed)


def _fetch_today_veronica_events(user_id: str) -> list[dict]:
    """Today's veronica_session rows for a user from user_events."""
    from nq_api.cache.score_cache import _supabase_rest

    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00")
    # Filters MUST go through query= — _supabase_rest passes them as httpx
    # params; a query string embedded in the table arg gets stripped.
    result = _supabase_rest(
        "user_events",
        method="GET",
        query={
            "user_id": f"eq.{user_id}",
            "event_type": "eq.veronica_session",
            "created_at": f"gte.{today}",
            "select": "label,payload",
        },
    )
    return result if isinstance(result, list) else []


def _veronica_seconds_today(user_id: str) -> int:
    """Sum today's usage. Orphan starts count ORPHAN_SESSION_S each.

    Fails open (0) — a Supabase blip must not lock users out.
    """
    try:
        rows = _fetch_today_veronica_events(user_id)
    except Exception:
        log.warning("Veronica cap check failed open for %s", user_id, exc_info=True)
        return 0
    starts = sum(1 for r in rows if r.get("label") == "session_start")
    ends = [r for r in rows if r.get("label") == "session_end"]
    total = 0
    for r in ends:
        payload = r.get("payload") or {}
        try:
            total += int(payload.get("duration_s", 0))
        except (TypeError, ValueError):
            pass
    total += max(0, starts - len(ends)) * ORPHAN_SESSION_S
    return total


def _is_first_veronica_today(user_id: str) -> bool:
    """True if the user has no prior veronica session today (drives the morning
    briefing). Must be called BEFORE _log_session_start. Fails closed (False)."""
    try:
        rows = _fetch_today_veronica_events(user_id)
    except Exception:
        return False
    return not any(r.get("label") == "session_start" for r in rows)


def _log_session_start(user_id: str | None, room: str, agent: str) -> None:
    """Best-effort usage logging to user_events."""
    try:
        from nq_api.cache.score_cache import _supabase_rest

        # "astra_session" is the historical name the web analytics layer
        # also emits — keep it so dashboards see one event stream.
        event_type = "veronica_session" if agent == "veronica" else "astra_session"
        _supabase_rest(
            "user_events",
            "POST",
            body=[{
                "user_id": user_id,
                "session_id": room,
                "event_type": event_type,
                "category": "voice",
                "label": "session_start",
                "payload": {"room": room, "authenticated": bool(user_id)},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }],
        )
    except Exception:
        log.debug("%s session analytics failed (non-critical)", agent)


async def _dispatch_agent(room: str) -> None:
    """Dispatch the worker to a room.

    The worker registers ONE agent name ('quantastra') and routes
    personas (QuantAstra vs Veronica) by room name prefix internally —
    do not invent a separate 'veronica' agent name here.
    """
    lk_api = LiveKitAPI(
        url=LIVEKIT_API_URL,
        api_key=LIVEKIT_KEY,
        api_secret=LIVEKIT_SECRET,
    )
    try:
        dispatch_req = CreateAgentDispatchRequest(
            agent_name="quantastra",
            room=room,
            metadata="",
        )
        dispatch = await lk_api.agent_dispatch.create_dispatch(dispatch_req)
        log.info(
            "Agent dispatch created: room=%s dispatch_id=%s state=%s",
            room,
            getattr(dispatch, "id", "unknown"),
            getattr(dispatch, "state", "unknown"),
        )
    finally:
        await lk_api.aclose()


@router.post("/livekit/token")
async def generate_token(
    request: Request, user=Depends(get_current_user_optional)
):
    """Generate a LiveKit access token.

    Default (no body, or any agent other than "veronica"): QuantAstra
    behavior — authenticated users get a room scoped to their user ID,
    guests get an anonymous room with a random UUID.

    body {"agent": "veronica"}: requires auth, room is
    `veronica-{user_id}`, gated by a 30 min/day usage cap.

    Also dispatches the quantastra agent worker to the room via the
    LiveKit AgentDispatch API so the agent joins automatically.
    """
    agent = "quantastra"
    try:
        body = await request.json()
        if isinstance(body, dict) and body.get("agent") == "veronica":
            agent = "veronica"
    except Exception:
        pass  # no/invalid body -> QuantAstra default

    if agent == "veronica":
        if not user:
            raise HTTPException(
                status_code=401, detail="Sign in to meet Veronica."
            )
        if _veronica_seconds_today(str(user.id)) >= VERONICA_DAILY_CAP_S:
            raise HTTPException(
                status_code=429,
                detail="Veronica needs a break — you've used today's voice "
                       "time. She'll be back tomorrow.",
            )
        user_id = str(user.id)
        room = f"veronica-{user_id}"
        morning_briefing = _is_first_veronica_today(user_id)
    else:
        user_id = str(user.id) if user else f"anonymous-{uuid.uuid4().hex[:8]}"
        room = f"quantastra-{user_id}"
        morning_briefing = False

    _log_session_start(str(user.id) if user else None, room, agent)

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

    # Dispatch the agent worker to the room.
    # Without this, the worker registers but never receives room events.
    try:
        await _dispatch_agent(room)
    except Exception:
        log.exception("Failed to create agent dispatch for room=%s", room)
        # Don't fail the request — user can still connect, agent may join
        # via retry or the 15s frontend timeout will show a message

    return {
        "token": token,
        "url": LIVEKIT_URL,
        "room": room,
        "morning_briefing": morning_briefing,
    }

"""Session tracking APIs — start/end sessions, log activities, retrieve reports.

POST /session/start     — create new session, return session_id
POST /session/activity  — log one or more activity events
POST /session/end       — close session, trigger analysis + email
GET  /session/reports   — list past session reports
GET  /session/report/{id} — get full report text
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from nq_api.auth import User, get_current_user_optional
from nq_api.cache.score_cache import _supabase_rest

log = logging.getLogger(__name__)

router = APIRouter(prefix="/session", tags=["session"])


# ── Request/Response models ──────────────────────────────────────────────

class SessionStartRequest(BaseModel):
    user_agent: Optional[str] = None
    metadata: Optional[dict] = Field(default_factory=dict)


class SessionStartResponse(BaseModel):
    session_id: str
    started_at: str


class ActivityEntry(BaseModel):
    activity_type: str
    category: str
    label: Optional[str] = None
    payload: Optional[dict] = Field(default_factory=dict)


class ActivityLogRequest(BaseModel):
    session_id: str
    activities: list[ActivityEntry]


class SessionEndRequest(BaseModel):
    session_id: str


class SessionReportSummary(BaseModel):
    id: str
    session_id: str
    summary: Optional[str]
    email_sent: bool
    generated_at: Optional[str]
    started_at: Optional[str] = None
    duration_minutes: Optional[int] = None


# ── Helpers ───────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _guest_id(request: Request) -> str:
    """Generate stable guest ID from IP hash."""
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else "unknown"
    )
    import hashlib, uuid
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"guest-{ip}"))


# ── Routes ────────────────────────────────────────────────────────────────

@router.post("/start", response_model=SessionStartResponse)
def start_session(
    body: SessionStartRequest,
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Create a new user session. Called on login or first activity."""
    user_id = user.id if user else _guest_id(request)

    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else None
    )

    metadata = body.metadata or {}
    if user and user.email:
        metadata["email"] = user.email

    payload = {
        "user_id": str(user_id),
        "started_at": _now_iso(),
        "user_agent": body.user_agent,
        "ip_address": ip,
        "is_guest": user is None,
        "metadata": metadata,
    }

    try:
        result = _supabase_rest(
            "user_sessions",
            method="POST",
            body=[payload],
        )
        if isinstance(result, list) and len(result) > 0:
            row = result[0]
            return SessionStartResponse(
                session_id=row["id"],
                started_at=row["started_at"],
            )
        raise HTTPException(500, "Failed to create session")
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Failed to create session")
        raise HTTPException(500, f"Failed to create session: {str(e)}")


@router.post("/activity")
def log_activity(
    body: ActivityLogRequest,
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Log one or more activity events for a session. Accepts batch."""
    user_id = user.id if user else _guest_id(request)

    rows = []
    for entry in body.activities:
        rows.append({
            "session_id": body.session_id,
            "user_id": str(user_id),
            "activity_type": entry.activity_type,
            "category": entry.category,
            "label": entry.label,
            "payload": entry.payload or {},
            "created_at": _now_iso(),
        })

    if not rows:
        return {"logged": 0}

    try:
        _supabase_rest(
            "session_activities",
            method="POST",
            body=rows,
        )
        return {"logged": len(rows)}
    except Exception as e:
        log.exception("Failed to log activities")
        raise HTTPException(500, f"Failed to log activities: {str(e)}")


@router.post("/end")
def end_session(
    body: SessionEndRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Close a session and trigger analysis + email generation."""
    # Fetch session by ID alone — beforeunload sendBeacon has no auth header,
    # so we can't filter by user_id. Session IDs are unguessable UUIDs.
    try:
        sessions = _supabase_rest(
            "user_sessions",
            method="GET",
            query={"id": f"eq.{body.session_id}", "select": "*"},
        )
    except Exception:
        sessions = []

    session_row = sessions[0] if isinstance(sessions, list) and sessions else None
    if not session_row:
        raise HTTPException(404, "Session not found")

    # If caller is authenticated, verify they own this session
    if user:
        stored_user_id = session_row.get("user_id")
        if stored_user_id and str(stored_user_id) != str(user.id):
            raise HTTPException(403, "Session does not belong to this user")

    started_at = session_row.get("started_at")
    ended_at = _now_iso()

    # Calculate duration
    duration_seconds = None
    if started_at:
        try:
            st = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            et = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
            duration_seconds = int((et - st).total_seconds())
        except Exception:
            pass

    # Mark session ended
    try:
        _supabase_rest(
            "user_sessions",
            method="PATCH",
            query={"id": f"eq.{body.session_id}"},
            body=[{
                "ended_at": ended_at,
                "duration_seconds": duration_seconds,
            }],
        )
    except Exception as e:
        log.exception("Failed to end session")
        raise HTTPException(500, f"Failed to end session: {str(e)}")

    # Resolve email: current auth user first, then session metadata (for beforeunload)
    email = None
    if user and user.email:
        email = user.email
    if not email:
        email = session_row.get("metadata", {}).get("email")

    stored_uid = session_row.get("user_id")
    name = email.split("@")[0] if email else None

    if email and duration_seconds and duration_seconds > 30:
        from nq_api.session_analysis import analyze_and_email
        background_tasks.add_task(
            analyze_and_email,
            session_id=body.session_id,
            user_id=str(stored_uid),
            user_email=email,
            user_name=name,
            duration_seconds=duration_seconds,
        )

    return {
        "session_id": body.session_id,
        "ended_at": ended_at,
        "duration_seconds": duration_seconds,
        "report_will_generate": bool(email and duration_seconds and duration_seconds > 30),
    }


@router.get("/reports", response_model=list[SessionReportSummary])
def list_reports(user: Optional[User] = Depends(get_current_user_optional)):
    """List all session reports for the current user."""
    if not user:
        raise HTTPException(401, "Authentication required to view reports")

    try:
        reports = _supabase_rest(
            "session_reports",
            method="GET",
            query={
                "user_id": f"eq.{user.id}",
                "select": "id,session_id,summary,email_sent,generated_at",
                "order": "generated_at.desc",
                "limit": "20",
            },
        )
        if not isinstance(reports, list):
            return []

        # Enrich with session start time
        result = []
        for r in reports:
            entry = SessionReportSummary(
                id=r["id"],
                session_id=r["session_id"],
                summary=r.get("summary"),
                email_sent=r.get("email_sent", False),
                generated_at=r.get("generated_at"),
            )
            # Try to get session started_at
            try:
                sessions = _supabase_rest(
                    "user_sessions",
                    method="GET",
                    query={
                        "id": f"eq.{r['session_id']}",
                        "select": "started_at,duration_seconds",
                    },
                )
                if isinstance(sessions, list) and sessions:
                    entry.started_at = sessions[0].get("started_at")
                    ds = sessions[0].get("duration_seconds")
                    if ds:
                        entry.duration_minutes = round(ds / 60)
            except Exception:
                pass
            result.append(entry)
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Failed to list reports")
        raise HTTPException(500, f"Failed to list reports: {str(e)}")


@router.get("/report/{report_id}")
def get_report(report_id: str, user: Optional[User] = Depends(get_current_user_optional)):
    """Get full report text for a session."""
    if not user:
        raise HTTPException(401, "Authentication required to view reports")

    try:
        reports = _supabase_rest(
            "session_reports",
            method="GET",
            query={
                "id": f"eq.{report_id}",
                "user_id": f"eq.{user.id}",
                "select": "*",
            },
        )
        if not isinstance(reports, list) or not reports:
            raise HTTPException(404, "Report not found")

        r = reports[0]
        return {
            "id": r["id"],
            "session_id": r["session_id"],
            "summary": r.get("summary"),
            "report_text": r.get("report_text"),
            "email_sent": r.get("email_sent", False),
            "generated_at": r.get("generated_at"),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Failed to get report")
        raise HTTPException(500, f"Failed to get report: {str(e)}")

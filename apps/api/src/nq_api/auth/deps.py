"""FastAPI deps: get_current_user + optional variant.

Reads JWT from Authorization header, verifies, then fetches/creates
public.users row via direct httpx REST to PostgREST (avoids
RemoteProtocolError from supabase Python SDK in uvicorn asyncio).
"""
from __future__ import annotations
import logging
import os
import secrets

import httpx
from fastapi import Depends, Header, HTTPException, status

from .jwt_verify import verify_supabase_jwt, JWTVerificationError
from .models import User

logger = logging.getLogger(__name__)


def _rest(
    method: str,
    table: str,
    query: dict[str, str] | None = None,
    body: dict | list | None = None,
) -> dict | list | None:
    """Direct httpx REST to PostgREST — avoids supabase SDK RemoteProtocolError."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required")
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
        with httpx.Client(timeout=10) as c:
            if method == "GET":
                r = c.get(endpoint, params=query or {}, headers=headers)
            elif method == "POST":
                r = c.post(endpoint, params=query or {}, json=body, headers=headers)
            elif method == "PATCH":
                r = c.patch(endpoint, params=query or {}, json=body, headers=headers)
            else:
                raise ValueError(f"unsupported method {method}")
            r.raise_for_status()
            return r.json() if r.content else None
    except httpx.HTTPStatusError as exc:
        logger.warning("PostgREST %s %s -> %s: %s", method, table, exc.response.status_code, exc.response.text[:200])
        raise
    except Exception as exc:
        logger.exception("PostgREST %s %s failed", method, table)
        raise


def _supabase_service_client():
    """Legacy compat — routes still importing this get a thin wrapper over _rest.
    Prefer using _rest() directly for new code."""
    import threading
    _tls = threading.local()
    client = getattr(_tls, "supabase_client", None)
    if client is not None:
        return client
    try:
        from supabase import create_client  # type: ignore
    except ImportError as exc:
        raise RuntimeError("supabase package missing") from exc
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required")
    client = create_client(url, key)
    _tls.supabase_client = client
    return client


def admin_emails() -> set[str]:
    """Allowlist of admin emails from the ADMIN_EMAILS env (comma-separated)."""
    raw = os.environ.get("ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def require_admin(user: User) -> None:
    """True admin gate — an allowlist of emails (ADMIN_EMAILS env), NOT the
    subscription tier. A paying pro/api customer is not an admin and must not
    see platform-wide metrics, other users' data, or internal ops tooling.

    Fail-closed: if ADMIN_EMAILS is unset, no one is admin."""
    admins = admin_emails()
    if not admins or (user.email or "").strip().lower() not in admins:
        from .security_audit import record
        record("admin_denied", email=user.email, detail="require_admin rejected non-allowlisted user")
        raise HTTPException(status_code=403, detail="Admin access required")


def require_team_access(
    authorization: str | None = Header(default=None),
    x_team_token: str | None = Header(default=None),
) -> User | None:
    """Gate the internal Team Hub (tasks/standups). Two ways in:

    1. Automation/agents: send `X-Team-Token` matching the TEAM_API_TOKEN env
       (constant-time compared). No JWT needed.
    2. Humans: a valid Supabase JWT whose email is in the ADMIN_EMAILS allowlist.

    Customers (any other signed-up user) are denied — the board is internal."""
    service_token = os.environ.get("TEAM_API_TOKEN", "")
    if service_token and x_team_token and secrets.compare_digest(x_team_token, service_token):
        return None  # authorized automation
    user = get_current_user(authorization)  # raises 401 if missing/invalid JWT
    require_admin(user)  # raises 403 if not allowlisted
    return user


def _smoke_bypass_ok(provided: str | None) -> bool:
    """Only honor the smoke bypass when a STRONG secret (>=24 chars) is set and
    matches. Prevents a weak/empty SMOKE_TEST_SECRET from enabling the bypass."""
    secret = os.environ.get("SMOKE_TEST_SECRET", "")
    return bool(secret) and len(secret) >= 24 and provided == secret


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def _load_user_row(user_id: str, email: str) -> dict:
    """Fetch users row; insert default tier='free' if missing."""
    try:
        rows = _rest("GET", "users", query={"select": "*", "id": f"eq.{user_id}"})
    except Exception as e:
        logger.debug("Non-critical enrichment failed: %s", e)
        rows = None
    if rows:
        return rows[0]
    # Fallback — trigger normally creates this, but insert defensively
    try:
        _rest("POST", "users", body={"id": user_id, "email": email, "tier": "free"})
    except Exception as e:
        logger.debug("Non-critical enrichment failed: %s", e)
        pass  # FK constraint or duplicate — return minimal row
    else:
        # New user — send welcome email (best-effort, never blocks)
        try:
            from nq_api.notify import send_welcome_email
            send_welcome_email(email)
        except Exception:
            logger.debug("Welcome email dispatch failed for %s (non-fatal)", email, exc_info=True)
    return {"id": user_id, "email": email, "tier": "free"}


def get_current_user(
    authorization: str | None = Header(default=None),
) -> User:
    """Require a valid Supabase JWT — raise 401 otherwise."""
    token = _extract_bearer(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = verify_supabase_jwt(token)
    except JWTVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = claims.get("sub")
    email = claims.get("email") or claims.get("user_metadata", {}).get("email") or ""
    if not user_id:
        raise HTTPException(status_code=401, detail="token missing sub")

    row = _load_user_row(user_id, email)
    return User(
        id=row["id"],
        email=row.get("email", email),
        tier=row.get("tier", "free"),
        paypal_subscription_id=row.get("paypal_subscription_id"),
        subscription_status=row.get("subscription_status"),
        referral_bonus_queries=row.get("referral_bonus_queries", 0),
    )


def get_current_user_optional(
    x_smoke_secret: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> User | None:
    """Return user if token valid, else None (no raise).
    Also accepts X-Smoke-Secret for automated smoke tests."""
    if _smoke_bypass_ok(x_smoke_secret):
        return User(
            id="smoke-test-00000000-0000-0000-0000-000000000000",
            email="smoke-test@neuralquant.internal",
            tier="pro",
            paypal_subscription_id=None,
            subscription_status="active",
            referral_bonus_queries=0,
        )
    if not _extract_bearer(authorization):
        return None
    try:
        return get_current_user(authorization)
    except HTTPException:
        return None


def get_current_user_smoke(
    x_smoke_secret: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> User:
    """Auth dependency that bypasses auth when X-Smoke-Secret matches
    SMOKE_TEST_SECRET env var. Used by smoke-test scripts for automated
    endpoint verification. Falls back to normal JWT auth otherwise."""
    if _smoke_bypass_ok(x_smoke_secret):
        # Smoke test bypass — return a synthetic pro-tier user
        return User(
            id="smoke-test-00000000-0000-0000-0000-000000000000",
            email="smoke-test@neuralquant.internal",
            tier="pro",
            paypal_subscription_id=None,
            subscription_status="active",
            referral_bonus_queries=0,
        )
    # No smoke secret match — require normal auth
    return get_current_user(authorization=authorization)
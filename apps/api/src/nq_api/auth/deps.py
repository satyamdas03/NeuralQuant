"""FastAPI deps: get_current_user + optional variant.

Reads JWT from Authorization header, verifies, then fetches/creates
public.users row via direct httpx REST to PostgREST (avoids
RemoteProtocolError from supabase Python SDK in uvicorn asyncio).
"""
from __future__ import annotations
import logging
import os

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
        stripe_customer_id=row.get("stripe_customer_id"),
        stripe_subscription_id=row.get("stripe_subscription_id"),
        subscription_status=row.get("subscription_status"),
        referral_bonus_queries=row.get("referral_bonus_queries", 0),
    )


def get_current_user_optional(
    authorization: str | None = Header(default=None),
) -> User | None:
    """Return user if token valid, else None (no raise)."""
    if not _extract_bearer(authorization):
        return None
    try:
        return get_current_user(authorization)
    except HTTPException:
        return None
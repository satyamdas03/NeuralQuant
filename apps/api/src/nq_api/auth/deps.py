"""FastAPI deps: get_current_user + optional variant.

Reads JWT from Authorization header, verifies, then fetches/creates
public.users row via Supabase service client.
"""
from __future__ import annotations
import os
from functools import lru_cache

from fastapi import Depends, Header, HTTPException, status

from .jwt_verify import verify_supabase_jwt, JWTVerificationError
from .models import User


@lru_cache(maxsize=1)
def _supabase_service_client():
    """Lazy singleton — avoid import cost when auth unused."""
    try:
        from supabase import create_client  # type: ignore
    except ImportError as exc:
        raise RuntimeError("supabase package missing — run `uv sync`") from exc

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def _load_user_row(user_id: str, email: str) -> dict:
    """Fetch users row; insert default tier='free' if missing."""
    client = _supabase_service_client()
    resp = client.table("users").select("*").eq("id", user_id).execute()
    rows = resp.data or []
    if rows:
        return rows[0]
    # Fallback — trigger normally creates this, but insert defensively
    client.table("users").insert(
        {"id": user_id, "email": email, "tier": "free"}
    ).execute()
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

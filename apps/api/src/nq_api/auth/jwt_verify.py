"""Verify Supabase-issued JWTs (ES256/RS256 via JWKS, HS256 fallback)."""
from __future__ import annotations
import logging
import os
from functools import lru_cache
from typing import Any

import jwt  # PyJWT
from jwt import PyJWKClient

log = logging.getLogger(__name__)


class JWTVerificationError(Exception):
    pass


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient | None:
    url = os.environ.get("SUPABASE_JWKS_URL")
    if not url:
        supa = os.environ.get("SUPABASE_URL", "").rstrip("/")
        if supa:
            url = f"{supa}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(url, cache_keys=True) if url else None


def verify_supabase_jwt(token: str) -> dict[str, Any]:
    """
    Verify JWT from Supabase. Tries JWKS (ES256/RS256) first for modern
    asymmetric-key projects, falls back to HS256 shared secret for legacy.
    Returns decoded claims on success, raises JWTVerificationError on failure.
    """
    if not token:
        raise JWTVerificationError("empty token")

    audience = os.environ.get("SUPABASE_JWT_AUDIENCE", "authenticated")

    # ES256/RS256 path (asymmetric — modern Supabase JWT signing keys)
    client = _jwks_client()
    if client is not None:
        try:
            signing_key = client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256"],
                audience=audience,
                options={"require": ["exp", "sub"]},
            )
        except jwt.PyJWTError:
            pass  # fall through to HS256

    # HS256 path (legacy shared secret)
    secret = os.environ.get("SUPABASE_JWT_SECRET", "").strip()
    if secret:
        try:
            return jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience=audience,
                options={"require": ["exp", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise JWTVerificationError("token verification failed") from exc

    raise JWTVerificationError("no JWKS available and no SUPABASE_JWT_SECRET configured")

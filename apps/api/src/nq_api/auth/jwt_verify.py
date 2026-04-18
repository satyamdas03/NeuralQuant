"""Verify Supabase-issued JWTs (HS256 shared-secret or ES256 via JWKS)."""
from __future__ import annotations
import os
from functools import lru_cache
from typing import Any

import jwt  # PyJWT
from jwt import PyJWKClient


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
    Verify JWT from Supabase. Tries HS256 (legacy shared secret) first,
    falls back to ES256 via JWKS for modern asymmetric-key projects.
    Returns decoded claims on success, raises JWTVerificationError on failure.
    """
    if not token:
        raise JWTVerificationError("empty token")

    audience = os.environ.get("SUPABASE_JWT_AUDIENCE", "authenticated")
    secret = os.environ.get("SUPABASE_JWT_SECRET", "").strip()

    # HS256 path (legacy — still the default for most Supabase projects)
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
            hs_err = exc
    else:
        hs_err = None

    # ES256 path (asymmetric — modern Supabase JWT signing keys)
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
        except jwt.PyJWTError as exc:
            raise JWTVerificationError(f"jwks verify failed: {exc}") from exc

    if hs_err is not None:
        raise JWTVerificationError(f"hs256 verify failed: {hs_err}") from hs_err
    raise JWTVerificationError("no SUPABASE_JWT_SECRET and no JWKS available")

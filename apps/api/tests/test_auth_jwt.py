"""Tests for Supabase JWT verification."""
import os
import time
import pytest
import jwt as pyjwt

from nq_api.auth.jwt_verify import verify_supabase_jwt, JWTVerificationError


SECRET = "test-secret-key-for-jwt-verification-min-length-32-chars"


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    monkeypatch.setenv("SUPABASE_JWT_AUDIENCE", "authenticated")
    # clear cached jwks client
    from nq_api.auth import jwt_verify
    jwt_verify._jwks_client.cache_clear()


def _make_token(overrides: dict | None = None, secret: str = SECRET) -> str:
    now = int(time.time())
    claims = {
        "sub": "user-123",
        "email": "test@example.com",
        "aud": "authenticated",
        "iat": now,
        "exp": now + 3600,
    }
    if overrides:
        claims.update(overrides)
    return pyjwt.encode(claims, secret, algorithm="HS256")


def test_valid_token_passes():
    token = _make_token()
    claims = verify_supabase_jwt(token)
    assert claims["sub"] == "user-123"
    assert claims["email"] == "test@example.com"


def test_expired_token_rejected():
    token = _make_token({"exp": int(time.time()) - 10})
    with pytest.raises(JWTVerificationError):
        verify_supabase_jwt(token)


def test_bad_signature_rejected():
    token = _make_token(secret="WRONG-SECRET-8675309-WRONG-SECRET-8675309")
    with pytest.raises(JWTVerificationError):
        verify_supabase_jwt(token)


def test_missing_sub_rejected():
    now = int(time.time())
    # PyJWT won't let us skip required claim via encode — encode without sub then decode
    token = pyjwt.encode(
        {"aud": "authenticated", "iat": now, "exp": now + 3600, "email": "x@y.z"},
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(JWTVerificationError):
        verify_supabase_jwt(token)


def test_empty_token_rejected():
    with pytest.raises(JWTVerificationError):
        verify_supabase_jwt("")

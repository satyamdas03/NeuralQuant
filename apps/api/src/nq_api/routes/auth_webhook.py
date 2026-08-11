"""Supabase auth webhook — no-op after email removal.

Supabase may still be configured to fire INSERT events on auth.users to this
endpoint. We keep the endpoint alive and verify the signature so the webhook
logs stay clean, but we do not send any emails.
"""
from __future__ import annotations
import hashlib
import hmac
import logging
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth-webhooks"])


class AuthEvent(BaseModel):
    type: str = ""  # "auth.user.created", etc.
    record: dict | None = None
    schema_name: str = ""
    table: str = ""
    old_record: dict | None = None


async def _verify_webhook_signature(request: Request) -> None:
    """Verify Supabase webhook HMAC-SHA256 signature.

    Requires SUPABASE_WEBHOOK_SECRET env var. If not set, webhook is disabled.
    """
    secret = os.environ.get("SUPABASE_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="webhook not configured")

    sig = request.headers.get("x-supabase-signature", "")
    if not sig:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing signature")

    body = await request.body()
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid signature")


@router.post("/webhook")
async def supabase_auth_webhook(
    request: Request,
    event: AuthEvent,
    _verified: None = Depends(_verify_webhook_signature),
):
    """Receive Supabase auth webhook events. HMAC signature verified.

    Emails are disabled, so this endpoint acknowledges the event and exits.
    Configure in Supabase Dashboard → Database → Webhooks:
    - Table: auth.users
    - Events: INSERT
    - Type: HTTP
    - URL: https://neuralquant.onrender.com/auth/webhook
    - Secret: SUPABASE_WEBHOOK_SECRET env var value
    """
    if event.type != "INSERT" and "created" not in event.type.lower():
        logger.info("Ignoring auth event: %s", event.type)
        return {"status": "ignored"}

    record = event.record or {}
    email = record.get("email", "")
    user_id = record.get("id", "")
    logger.debug("Auth webhook received for %s (%s) — email disabled", email, user_id)
    return {"status": "ignored", "reason": "emails_disabled"}


@router.post("/welcome")
async def manual_welcome(
    request: Request,
):
    """Manual welcome trigger — disabled.

    The frontend used to call this after signup. It now returns a no-op status.
    Requires authentication.
    """
    from nq_api.auth.deps import get_current_user
    get_current_user(request.headers.get("Authorization"))
    return {"status": "ignored", "reason": "emails_disabled"}

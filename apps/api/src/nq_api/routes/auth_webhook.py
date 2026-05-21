"""Supabase auth webhook — sends welcome email sequence on signup.

Supabase fires an auth.user.created event that we can receive via webhook.
Configure in Supabase Dashboard → Database → Webhooks.

The /webhook endpoint verifies HMAC-SHA256 signature from x-supabase-signature header.
The /welcome endpoint requires user authentication.
"""
from __future__ import annotations
import hashlib
import hmac
import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
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
    background_tasks: BackgroundTasks,
    _verified: None = Depends(_verify_webhook_signature),
):
    """Receive Supabase auth webhook events. HMAC signature verified.

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
    raw_meta = record.get("raw_user_meta_data") or record.get("raw_user_meta_data", {}) or {}
    name = raw_meta.get("full_name") or raw_meta.get("name") or email.split("@")[0] if email else "there"

    if not email:
        logger.warning("Auth webhook: no email in record %s", user_id)
        return {"status": "no_email"}

    from nq_api.notify import send_welcome_email
    background_tasks.add_task(send_welcome_email, to=email, name=name)

    logger.info("Welcome email queued for %s (user %s)", email, user_id)
    return {"status": "queued"}


@router.post("/welcome")
async def manual_welcome(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Manual trigger for welcome email — called by frontend after signup.
    Requires authentication. Only sends to the authenticated user's own email.

    Body: {"email": "user@example.com", "name": "User Name"}
    """
    from nq_api.auth.deps import get_current_user
    user = get_current_user(request.headers.get("Authorization"))
    body = await request.json()
    email = body.get("email", "")
    name = body.get("name") or email.split("@")[0] if email else "there"

    if not email:
        return {"status": "error", "message": "email required"}
    if email.lower() != (user.email or "").lower():
        return {"status": "error", "message": "email does not match authenticated user"}

    from nq_api.notify import send_welcome_email
    background_tasks.add_task(send_welcome_email, to=email, name=name)

    logger.info("Manual welcome email queued for %s", email)
    return {"status": "queued"}
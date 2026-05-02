"""Supabase auth webhook — sends welcome email sequence on signup.

Supabase fires an auth.user.created event that we can receive via webhook.
Configure in Supabase Dashboard → Database → Webhooks.

Alternatively, the frontend can call POST /auth/welcome after signup.
"""
from __future__ import annotations
import logging
from fastapi import APIRouter, BackgroundTasks, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth-webhooks"])


class AuthEvent(BaseModel):
    type: str = ""  # "auth.user.created", etc.
    record: dict | None = None
    schema_name: str = ""
    table: str = ""
    old_record: dict | None = None


@router.post("/webhook")
async def supabase_auth_webhook(event: AuthEvent, background_tasks: BackgroundTasks):
    """Receive Supabase auth webhook events.

    Configure in Supabase Dashboard → Database → Webhooks:
    - Table: auth.users
    - Events: INSERT
    - Type: HTTP
    - URL: https://neuralquant.onrender.com/auth/webhook
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

    # Send welcome email in background
    from nq_api.notify import send_welcome_email
    background_tasks.add_task(send_welcome_email, to=email, name=name)

    logger.info("Welcome email queued for %s (user %s)", email, user_id)
    return {"status": "queued"}


@router.post("/welcome")
async def manual_welcome(request: Request, background_tasks: BackgroundTasks):
    """Manual trigger for welcome email — called by frontend after signup.

    Body: {"email": "user@example.com", "name": "User Name"}
    """
    body = await request.json()
    email = body.get("email", "")
    name = body.get("name") or email.split("@")[0] if email else "there"

    if not email:
        return {"status": "error", "message": "email required"}

    from nq_api.notify import send_welcome_email
    background_tasks.add_task(send_welcome_email, to=email, name=name)

    logger.info("Manual welcome email queued for %s", email)
    return {"status": "queued"}
"""PayPal webhook handler — updates user tier on subscription events.

Handles: BILLING.SUBSCRIPTION.ACTIVATED, CANCELLED, SUSPENDED, PAYMENT.SALE.COMPLETED
Uses direct httpx REST to PostgREST for user updates.
"""
import logging
import os

from fastapi import APIRouter, Request, HTTPException, Header

from nq_api.auth.deps import _rest
from nq_api.paypal import verify_webhook_signature

log = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/paypal")
async def paypal_webhook(request: Request):
    """Handle PayPal webhook events."""
    body = await request.body()
    headers = {
        "paypal-transmission-id": request.headers.get("paypal-transmission-id", ""),
        "paypal-transmission-time": request.headers.get("paypal-transmission-time", ""),
        "paypal-cert-url": request.headers.get("paypal-cert-url", ""),
        "paypal-auth-algo": request.headers.get("paypal-auth-algo", ""),
        "paypal-transmission-sig": request.headers.get("paypal-transmission-sig", ""),
    }

    # Verify webhook signature
    if not verify_webhook_signature(headers, body):
        log.warning("PayPal webhook signature verification failed")
        raise HTTPException(400, "Invalid signature")

    import json

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")

    event_type = event.get("event_type", "")

    if event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
        _handle_subscription_activated(event)
    elif event_type == "BILLING.SUBSCRIPTION.CANCELLED":
        _handle_subscription_cancelled(event)
    elif event_type == "BILLING.SUBSCRIPTION.SUSPENDED":
        _handle_subscription_suspended(event)
    elif event_type == "PAYMENT.SALE.COMPLETED":
        log.info("PayPal payment completed: %s", event.get("id", "unknown"))
    else:
        log.info("PayPal webhook unhandled event type: %s", event_type)

    return {"received": True}


def _handle_subscription_activated(event: dict):
    """New PayPal subscription activated — update tier."""
    resource = event.get("resource", {})
    subscription_id = resource.get("id", "")
    metadata = resource.get("metadata", {})
    user_id = metadata.get("user_id")
    tier = metadata.get("tier", "investor")

    if not user_id:
        # Fallback: try to find user by subscriber email
        subscriber = resource.get("subscriber", {})
        email = subscriber.get("email_address", "")
        if email:
            try:
                rows = _rest("GET", "users", query={"select": "id", "email": f"eq.{email}"})
                if rows:
                    user_id = rows[0]["id"]
            except Exception:
                pass

    if not user_id:
        log.warning("PayPal subscription activated but no user_id found: %s", subscription_id)
        return

    try:
        _rest("PATCH", "users", query={"id": f"eq.{user_id}"}, body={
            "tier": tier,
            "paypal_subscription_id": subscription_id,
            "subscription_status": "active",
        })
        log.info("PayPal subscription activated: user=%s tier=%s sub=%s", user_id, tier, subscription_id)
    except Exception as e:
        log.error("Failed to update user tier on PayPal activation: %s", e)


def _handle_subscription_cancelled(event: dict):
    """PayPal subscription cancelled — downgrade to free."""
    resource = event.get("resource", {})
    subscription_id = resource.get("id", "")

    try:
        rows = _rest("GET", "users", query={"select": "id", "paypal_subscription_id": f"eq.{subscription_id}"})
    except Exception:
        rows = None

    if not rows:
        log.warning("PayPal subscription cancelled but no user found for sub=%s", subscription_id)
        return

    user_id = rows[0]["id"]
    try:
        _rest("PATCH", "users", query={"id": f"eq.{user_id}"}, body={
            "tier": "free",
            "subscription_status": "cancelled",
        })
        log.info("PayPal subscription cancelled: user=%s", user_id)
    except Exception as e:
        log.error("Failed to downgrade user on PayPal cancellation: %s", e)


def _handle_subscription_suspended(event: dict):
    """PayPal subscription suspended (payment issue) — mark as past_due."""
    resource = event.get("resource", {})
    subscription_id = resource.get("id", "")

    try:
        rows = _rest("GET", "users", query={"select": "id", "paypal_subscription_id": f"eq.{subscription_id}"})
    except Exception:
        rows = None

    if not rows:
        return

    user_id = rows[0]["id"]
    try:
        _rest("PATCH", "users", query={"id": f"eq.{user_id}"}, body={
            "subscription_status": "past_due",
        })
        log.info("PayPal subscription suspended: user=%s", user_id)
    except Exception as e:
        log.error("Failed to update user on PayPal suspension: %s", e)
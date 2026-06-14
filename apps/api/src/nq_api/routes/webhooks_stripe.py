"""Stripe webhook handler — updates user tier on subscription events.

Handles: checkout.session.completed, customer.subscription.updated,
customer.subscription.deleted, invoice.payment_failed

Uses direct httpx REST to PostgREST for user updates (same pattern as PayPal).
"""
import logging
import os

import stripe
from fastapi import APIRouter, Request, HTTPException, Header

from nq_api.auth.deps import _rest

log = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks-stripe"])

_stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
if _stripe_key:
    stripe.api_key = _stripe_key

_stripe_webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


@router.post("/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    body = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not _stripe_webhook_secret:
        # An unverified webhook lets anyone forge tier upgrades / cancellations.
        # Fail closed in production; only allow the unsigned path when explicitly
        # opted in for local dev (ALLOW_UNVERIFIED_STRIPE_WEBHOOK=true).
        if os.environ.get("ALLOW_UNVERIFIED_STRIPE_WEBHOOK", "").lower() != "true":
            log.error("STRIPE_WEBHOOK_SECRET not set — refusing unverified webhook")
            from nq_api.auth.security_audit import record
            record("stripe_webhook_unconfigured", severity="critical",
                   detail="received webhook with no STRIPE_WEBHOOK_SECRET configured")
            raise HTTPException(503, "Webhook verification not configured")
        log.warning("STRIPE_WEBHOOK_SECRET not set — accepting UNVERIFIED webhook (dev opt-in)")
        import json
        try:
            event = json.loads(body)
        except Exception:
            raise HTTPException(400, "Invalid JSON")
    else:
        try:
            event = stripe.Webhook.construct_event(
                body, sig_header, _stripe_webhook_secret
            )
        except stripe.error.SignatureVerificationError:
            log.warning("Stripe webhook signature verification failed")
            from nq_api.auth.security_audit import record
            record("stripe_webhook_bad_signature", severity="critical",
                   detail="signature verification failed")
            raise HTTPException(400, "Invalid signature")
        except Exception as e:
            log.error("Stripe webhook parsing error: %s", e)
            raise HTTPException(400, f"Webhook error: {e}")

    event_type = event.get("type", "")
    log.info("Stripe webhook event: %s", event_type)

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(event)
    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(event)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(event)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(event)
    else:
        log.info("Stripe webhook unhandled event type: %s", event_type)

    return {"received": True}


def _handle_checkout_completed(event: dict):
    """New Stripe checkout completed — update tier and Stripe customer ID."""
    session = event.get("data", {}).get("object", {})
    metadata = session.get("metadata", {})
    user_id = metadata.get("user_id")
    tier = metadata.get("tier", "investor")

    # Get Stripe customer ID
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    if not user_id:
        # Fallback: find user by email from customer
        if customer_id:
            try:
                customer = stripe.Customer.retrieve(customer_id)
                email = customer.get("email", "")
                if email:
                    rows = _rest("GET", "users", query={"select": "id", "email": f"eq.{email}"})
                    if rows:
                        user_id = rows[0]["id"]
            except Exception as e:
                log.error("Stripe customer lookup failed: %s", e)

    if not user_id:
        log.warning("Stripe checkout completed but no user_id found: session=%s", session.get("id"))
        return

    try:
        _rest("PATCH", "users", query={"id": f"eq.{user_id}"}, body={
            "tier": tier,
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
            "subscription_status": "active",
        })
        log.info("Stripe checkout activated: user=%s tier=%s sub=%s", user_id, tier, subscription_id)
    except Exception as e:
        log.error("Failed to update user tier on Stripe activation: %s", e)


def _handle_subscription_updated(event: dict):
    """Stripe subscription updated (plan change, etc.)."""
    subscription = event.get("data", {}).get("object", {})
    subscription_id = subscription.get("id")
    metadata = subscription.get("metadata", {})
    tier = metadata.get("tier", "investor")

    # Find user by stripe_subscription_id
    try:
        rows = _rest("GET", "users", query={
            "select": "id",
            "stripe_subscription_id": f"eq.{subscription_id}",
        })
    except Exception:
        rows = None

    if not rows:
        log.warning("Stripe subscription updated but no user found for sub=%s", subscription_id)
        return

    user_id = rows[0]["id"]
    try:
        _rest("PATCH", "users", query={"id": f"eq.{user_id}"}, body={
            "tier": tier,
            "subscription_status": "active",
        })
        log.info("Stripe subscription updated: user=%s tier=%s", user_id, tier)
    except Exception as e:
        log.error("Failed to update user on Stripe subscription update: %s", e)


def _handle_subscription_deleted(event: dict):
    """Stripe subscription cancelled/deleted — downgrade to free."""
    subscription = event.get("data", {}).get("object", {})
    subscription_id = subscription.get("id")

    try:
        rows = _rest("GET", "users", query={
            "select": "id",
            "stripe_subscription_id": f"eq.{subscription_id}",
        })
    except Exception:
        rows = None

    if not rows:
        log.warning("Stripe subscription deleted but no user found for sub=%s", subscription_id)
        return

    user_id = rows[0]["id"]
    try:
        _rest("PATCH", "users", query={"id": f"eq.{user_id}"}, body={
            "tier": "free",
            "subscription_status": "cancelled",
        })
        log.info("Stripe subscription cancelled: user=%s", user_id)
    except Exception as e:
        log.error("Failed to downgrade user on Stripe cancellation: %s", e)


def _handle_payment_failed(event: dict):
    """Stripe payment failed — mark as past_due."""
    invoice = event.get("data", {}).get("object", {})
    customer_id = invoice.get("customer")

    if not customer_id:
        return

    try:
        rows = _rest("GET", "users", query={
            "select": "id",
            "stripe_customer_id": f"eq.{customer_id}",
        })
    except Exception:
        return

    if not rows:
        return

    user_id = rows[0]["id"]
    try:
        _rest("PATCH", "users", query={"id": f"eq.{user_id}"}, body={
            "subscription_status": "past_due",
        })
        log.info("Stripe payment failed: user=%s marked past_due", user_id)
    except Exception as e:
        log.error("Failed to update user on Stripe payment failure: %s", e)
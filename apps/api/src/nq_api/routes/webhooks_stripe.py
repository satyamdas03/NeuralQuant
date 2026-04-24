"""Stripe webhook handler — updates user tier on payment events."""
import os
import stripe
from fastapi import APIRouter, Request, HTTPException, Header

from nq_api.auth.deps import _supabase_service_client

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(alias="Stripe-Signature"),
):
    """Handle Stripe webhook events."""
    body = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            body, stripe_signature, WEBHOOK_SECRET,
        )
    except (stripe.error.SignatureVerificationError, ValueError):
        raise HTTPException(400, "Invalid signature")

    if event["type"] == "checkout.session.completed":
        _handle_checkout_complete(event["data"]["object"])
    elif event["type"] == "customer.subscription.updated":
        _handle_subscription_update(event["data"]["object"])
    elif event["type"] == "customer.subscription.deleted":
        _handle_subscription_delete(event["data"]["object"])

    return {"received": True}


def _handle_checkout_complete(session: dict):
    """New subscription created — update tier + Stripe IDs."""
    user_id = session.get("metadata", {}).get("user_id")
    tier = session.get("metadata", {}).get("tier", "investor")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    if not user_id:
        return

    client = _supabase_service_client()
    client.table("users").update({
        "tier": tier,
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "subscription_status": "active",
    }).eq("id", user_id).execute()


def _handle_subscription_update(subscription: dict):
    """Subscription changed (upgrade/downgrade)."""
    customer_id = subscription.get("customer")
    status = subscription.get("status")

    client = _supabase_service_client()
    result = client.table("users").select("id").eq("stripe_customer_id", customer_id).execute()
    if not result.data:
        return

    user_id = result.data[0]["id"]
    client.table("users").update({
        "subscription_status": status,
    }).eq("id", user_id).execute()


def _handle_subscription_delete(subscription: dict):
    """Subscription cancelled — downgrade to free."""
    customer_id = subscription.get("customer")

    client = _supabase_service_client()
    result = client.table("users").select("id").eq("stripe_customer_id", customer_id).execute()
    if not result.data:
        return

    user_id = result.data[0]["id"]
    client.table("users").update({
        "tier": "free",
        "subscription_status": "cancelled",
    }).eq("id", user_id).execute()
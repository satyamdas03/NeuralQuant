"""Stripe Checkout session creation.

Creates Stripe Checkout Sessions for investor/pro/api tiers.
Runs alongside existing PayPal checkout — frontend chooses provider.
Supports regional pricing: IN prices for Indian users, US prices otherwise.
"""
import os
import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Query

from nq_api.auth.deps import get_current_user
from nq_api.auth.models import User

log = logging.getLogger(__name__)

router = APIRouter(prefix="/checkout/stripe", tags=["checkout-stripe"])

# Regional Stripe price IDs — IN (India) and US (rest of world)
STRIPE_PRICES_IN: dict[str, str] = {
    "investor": os.environ.get("STRIPE_PRICE_INVESTOR_IN", "") or os.environ.get("STRIPE_PRICE_INVESTOR", ""),
    "pro": os.environ.get("STRIPE_PRICE_PRO_IN", "") or os.environ.get("STRIPE_PRICE_PRO", ""),
    "api": os.environ.get("STRIPE_PRICE_MORGAN_IN", "") or os.environ.get("STRIPE_PRICE_API", ""),
}
STRIPE_PRICES_US: dict[str, str] = {
    "investor": os.environ.get("STRIPE_PRICE_INVESTOR_US", "") or os.environ.get("STRIPE_PRICE_INVESTOR", ""),
    "pro": os.environ.get("STRIPE_PRICE_PRO_US", "") or os.environ.get("STRIPE_PRICE_PRO", ""),
    "api": os.environ.get("STRIPE_PRICE_MORGAN_US", "") or os.environ.get("STRIPE_PRICE_API", ""),
}

# Stripe secret key
_stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
if _stripe_key:
    stripe.api_key = _stripe_key


@router.post("/session")
async def create_stripe_checkout_session(
    tier: str = Query(..., pattern=r"^(investor|pro|api)$"),
    currency: str = Query("USD", pattern=r"^(USD|INR)$"),
    user: User = Depends(get_current_user),
):
    """Create a Stripe Checkout session and return the redirect URL.

    Currency parameter selects regional pricing:
    - INR → India-specific Stripe prices (if configured)
    - USD → US/international Stripe prices (fallback)
    """
    if not _stripe_key:
        raise HTTPException(501, "Stripe is not configured")

    prices = STRIPE_PRICES_IN if currency == "INR" else STRIPE_PRICES_US
    price_id = prices.get(tier)
    if not price_id:
        # Fallback to generic price if regional not available
        fallback = os.environ.get(f"STRIPE_PRICE_{tier.upper()}", "")
        price_id = fallback
    if not price_id:
        raise HTTPException(400, f"No Stripe price configured for {tier} in {currency}")

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=os.environ.get(
                "STRIPE_SUCCESS_URL", "https://neuralquant.co/dashboard?upgraded=1"
            ),
            cancel_url=os.environ.get(
                "STRIPE_CANCEL_URL", "https://neuralquant.co/pricing?cancelled=1"
            ),
            client_reference_id=str(user.id),
            customer_email=user.email,
            metadata={
                "user_id": str(user.id),
                "tier": tier,
            },
            subscription_data={
                "metadata": {
                    "user_id": str(user.id),
                    "tier": tier,
                },
            },
        )
        return {"url": session.url}
    except stripe.error.StripeError as e:
        log.error("Stripe checkout session creation failed: %s", e)
        raise HTTPException(400, f"Stripe checkout failed: {e.user_message if hasattr(e, 'user_message') else str(e)}")


@router.post("/portal")
async def create_stripe_portal_session(
    user: User = Depends(get_current_user),
):
    """Create a Stripe Customer Portal session for managing subscriptions."""
    if not _stripe_key:
        raise HTTPException(501, "Stripe is not configured")

    # Find the Stripe customer for this user
    from nq_api.auth.deps import _rest

    users = _rest("GET", "users", query={"select": "stripe_customer_id", "id": f"eq.{user.id}"})
    customer_id = users[0].get("stripe_customer_id") if users else None

    if not customer_id:
        raise HTTPException(404, "No Stripe subscription found for this user")

    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=os.environ.get(
                "STRIPE_PORTAL_RETURN_URL", "https://neuralquant.co/dashboard"
            ),
        )
        return {"url": session.url}
    except stripe.error.StripeError as e:
        log.error("Stripe portal session creation failed: %s", e)
        raise HTTPException(400, f"Stripe portal failed: {str(e)}")
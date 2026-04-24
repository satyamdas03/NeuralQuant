"""Stripe Checkout Session creation."""
import os
from fastapi import APIRouter, Depends, HTTPException, Query
import stripe

from nq_api.auth.deps import get_current_user
from nq_api.auth.models import User, STRIPE_PRICES

router = APIRouter(prefix="/checkout", tags=["checkout"])

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
SUCCESS_URL = os.environ.get("STRIPE_SUCCESS_URL", "https://neuralquant.vercel.app/dashboard?upgraded=1")
CANCEL_URL = os.environ.get("STRIPE_CANCEL_URL", "https://neuralquant.vercel.app/pricing")


@router.post("/session")
async def create_checkout_session(
    tier: str = Query(..., pattern=r"^(investor|pro|api)$"),
    currency: str = Query("USD", pattern=r"^(INR|USD)$"),
    user: User = Depends(get_current_user),
):
    """Create a Stripe Checkout Session for the given tier + currency."""
    price_id = STRIPE_PRICES.get(tier, {}).get(currency)
    if not price_id:
        raise HTTPException(400, f"No price configured for {tier}/{currency}")

    # Reuse existing Stripe customer if available
    customer_kwargs = {}
    if user.stripe_customer_id:
        customer_kwargs["customer"] = user.stripe_customer_id
    else:
        customer_kwargs["customer_email"] = user.email

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=SUCCESS_URL,
            cancel_url=CANCEL_URL,
            metadata={"user_id": user.id, "tier": tier},
            **customer_kwargs,
        )
    except stripe.error.StripeError as e:
        raise HTTPException(400, str(e))

    return {"url": session.url, "session_id": session.id}
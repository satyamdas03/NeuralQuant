"""PayPal Subscription creation.

All payments processed in USD. INR prices shown on frontend are approximate.
PayPal doesn't support INR recurring billing.
"""
import os
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from nq_api.auth.deps import get_current_user
from nq_api.auth.models import User, PAYPAL_PRICES
from nq_api.paypal import create_subscription_link

log = logging.getLogger(__name__)

router = APIRouter(prefix="/checkout", tags=["checkout"])


@router.post("/session")
async def create_checkout_session(
    tier: str = Query(..., pattern=r"^(investor|pro|api)$"),
    currency: str = Query("USD", pattern=r"^(INR|USD)$"),
    user: User = Depends(get_current_user),
):
    """Create a PayPal subscription and return the approval URL.

    All payments are in USD. The currency param is accepted for
    backward compatibility but PayPal always charges USD.
    """
    plan_id = PAYPAL_PRICES.get(tier)
    if not plan_id:
        raise HTTPException(400, f"No plan configured for {tier}")

    try:
        approval_url = create_subscription_link(
            plan_id=plan_id,
            user_id=user.id,
            user_email=user.email,
            tier=tier,
        )
    except Exception as e:
        log.error("PayPal subscription creation failed: %s", e)
        raise HTTPException(400, f"Payment setup failed: {e}")

    return {"url": approval_url}
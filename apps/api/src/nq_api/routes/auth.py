"""GET /auth/me — return current user profile."""
from fastapi import APIRouter, Depends

from nq_api.auth import User, get_current_user
from nq_api.auth.models import TIER_LIMITS

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    limits = TIER_LIMITS.get(user.tier, TIER_LIMITS["free"])
    return {
        "id": user.id,
        "email": user.email,
        "tier": user.tier,
        "subscription_status": user.subscription_status,
        "limits": limits.model_dump(),
    }

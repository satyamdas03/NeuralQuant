"""GET /auth/me — return current user profile."""
from fastapi import APIRouter, Depends

from nq_api.auth import User, get_current_user
from nq_api.auth.models import TIER_LIMITS
from nq_api.cache.score_cache import _supabase_rest
from nq_api.schemas import UserProfile

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


@router.get("/me/profile", response_model=UserProfile | None)
def get_user_profile(user: User = Depends(get_current_user)):
    data = _supabase_rest(
        f"user_profiles?user_id=eq.{user.id}&select=*",
        method="GET"
    )
    if data and len(data) > 0:
        row = data[0]
        return UserProfile(
            risk_profile=row.get("risk_profile", ""),
            time_horizon=row.get("time_horizon", ""),
            goal=row.get("goal", ""),
            investable_amount=row.get("investable_amount"),
        )
    return None


@router.post("/me/profile", response_model=UserProfile)
def save_user_profile(profile: UserProfile, user: User = Depends(get_current_user)):
    payload = {
        "user_id": str(user.id),
        "risk_profile": profile.risk_profile,
        "time_horizon": profile.time_horizon,
        "goal": profile.goal,
        "investable_amount": profile.investable_amount,
        "updated_at": "now()",
    }
    _supabase_rest(
        "user_profiles",
        method="POST",
        body=[payload],
    )
    return profile

"""GET /auth/me — return current user profile."""
import logging
from fastapi import APIRouter, Depends

from nq_api.auth import User, get_current_user
from nq_api.auth.models import TIER_LIMITS
from nq_api.cache.score_cache import _supabase_rest
from nq_api.schemas import UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/stats")
def auth_stats(user: User = Depends(get_current_user)):
    """Return signup/traction analytics (admin only)."""
    if user.tier not in ("pro", "api"):
        from fastapi import HTTPException
        raise HTTPException(403, "Admin only")

    try:
        users = _supabase_rest(
            "/rest/v1/users?select=id,email,tier,created_at&order=created_at.desc&limit=100",
            method="GET",
        )
    except Exception as e:
        logger.exception("Failed to fetch user stats")
        users = []

    total = len(users)
    by_tier = {}
    for u in users:
        t = u.get("tier", "free")
        by_tier[t] = by_tier.get(t, 0) + 1

    return {
        "total_users": total,
        "by_tier": by_tier,
        "recent_signups": users[:10],
    }


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
        extra_headers={"Prefer": "return=representation,resolution=merge-duplicates"},
    )
    return profile

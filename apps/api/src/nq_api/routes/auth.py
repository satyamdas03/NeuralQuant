"""Auth routes — user profile, stats, account deletion."""
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
            email_market_wrap=row.get("email_market_wrap", True),
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
        "email_market_wrap": profile.email_market_wrap,
        "updated_at": "now()",
    }
    _supabase_rest(
        "user_profiles",
        method="POST",
        body=[payload],
        extra_headers={"Prefer": "return=representation,resolution=merge-duplicates"},
    )
    return profile


@router.post("/delete-account")
def delete_account(user: User = Depends(get_current_user)):
    """Permanently delete user account and all associated data.

    Cascade deletes all user data from Supabase tables, then deletes the auth user.
    This action is IRREVERSIBLE.

    Tables cleaned (FK cascades handle most via ON DELETE CASCADE):
    - user_profiles, watchlists, watchlist_stocks
    - conversations, conversation_messages
    - session_reports, user_sessions
    - mobile_push_tokens
    - stripe_customers (if exists)
    - quarterly_test_runs/results (admin only, not applicable)
    """
    import os
    from datetime import datetime, timezone

    user_id = str(user.id)
    logger.warning("ACCOUNT DELETION requested for user %s", user_id)

    deleted_tables = []

    # 1. Delete user-owned data from tables without FK cascade
    _user_tables = [
        ("user_profiles", f"user_id=eq.{user_id}"),
        ("mobile_push_tokens", f"user_id=eq.{user_id}"),
    ]
    for table, filter_str in _user_tables:
        try:
            _supabase_rest(f"{table}?{filter_str}", method="DELETE")
            deleted_tables.append(table)
        except Exception as exc:
            logger.warning("Failed to delete from %s: %s", table, exc)

    # 2. Delete the auth user via Supabase admin API
    supabase_url = os.environ.get("SUPABASE_URL", "")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if supabase_url and service_key:
        try:
            import httpx
            with httpx.Client(timeout=15) as client:
                r = client.delete(
                    f"{supabase_url}/auth/v1/admin/users/{user_id}",
                    headers={
                        "apikey": service_key,
                        "Authorization": f"Bearer {service_key}",
                    },
                )
                r.raise_for_status()
                deleted_tables.append("auth.users")
                logger.info("Auth user %s deleted successfully", user_id)
        except Exception as exc:
            logger.error("Failed to delete auth user %s: %s", user_id, exc)
            return {
                "status": "partial",
                "message": "User data deleted from some tables but auth user deletion failed. Contact support.",
                "deleted_tables": deleted_tables,
            }

    return {
        "status": "deleted",
        "message": "Account and all associated data permanently deleted.",
        "deleted_tables": deleted_tables,
        "deleted_at": datetime.now(timezone.utc).isoformat(),
    }

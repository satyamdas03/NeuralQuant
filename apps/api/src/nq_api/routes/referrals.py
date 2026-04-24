"""Referral code management."""
import hashlib
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from nq_api.auth.deps import get_current_user, _supabase_service_client
from nq_api.auth.models import User

router = APIRouter(prefix="/referrals", tags=["referrals"])


class ReferralCodeOut(BaseModel):
    code: str
    link: str
    total_referred: int
    bonus_queries: int


@router.get("/my-code", response_model=ReferralCodeOut)
async def get_my_code(user: User = Depends(get_current_user)):
    """Get or create referral code for current user."""
    client = _supabase_service_client()

    result = client.table("referrals").select("code, status").eq("referrer_id", user.id).eq("status", "active").execute()

    if result.data:
        code = result.data[0]["code"]
    else:
        code = "NQ-" + hashlib.sha256(user.id.encode()).hexdigest()[:7].upper()
        client.table("referrals").insert({
            "referrer_id": user.id,
            "code": code,
        }).execute()

    count_result = client.table("referrals").select("id", count="exact").eq("referrer_id", user.id).eq("status", "redeemed").execute()
    total_referred = count_result.count or 0

    site = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://neuralquant.vercel.app")
    link = f"{site}/signup?ref={code}"

    return ReferralCodeOut(
        code=code,
        link=link,
        total_referred=total_referred,
        bonus_queries=user.referral_bonus_queries,
    )
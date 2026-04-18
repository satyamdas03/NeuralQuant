"""User + Tier pydantic models for auth layer."""
from typing import Literal
from pydantic import BaseModel, EmailStr

Tier = Literal["free", "investor", "pro", "api"]


class User(BaseModel):
    """Authenticated user — from Supabase JWT + public.users row."""
    id: str
    email: str
    tier: Tier = "free"
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    subscription_status: str | None = None


class TierLimits(BaseModel):
    """Per-tier quotas."""
    watchlist_max: int
    queries_per_day: int
    backtest_per_day: int
    screener_refresh_seconds: int


TIER_LIMITS: dict[str, TierLimits] = {
    "free":     TierLimits(watchlist_max=5,  queries_per_day=10,  backtest_per_day=0,   screener_refresh_seconds=3600),
    "investor": TierLimits(watchlist_max=25, queries_per_day=100, backtest_per_day=5,   screener_refresh_seconds=300),
    "pro":      TierLimits(watchlist_max=100, queries_per_day=1000, backtest_per_day=50, screener_refresh_seconds=60),
    "api":      TierLimits(watchlist_max=1000, queries_per_day=100000, backtest_per_day=1000, screener_refresh_seconds=0),
}

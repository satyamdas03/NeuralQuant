"""User + Tier pydantic models for auth layer."""
import os
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
    referral_bonus_queries: int = 0


class TierLimits(BaseModel):
    """Per-tier quotas."""
    watchlist_max: int
    queries_per_day: int
    backtest_per_day: int
    screener_refresh_seconds: int


TIER_LIMITS: dict[str, TierLimits] = {
    "free":     TierLimits(watchlist_max=5,   queries_per_day=9999,   backtest_per_day=9999,  screener_refresh_seconds=3600),
    "investor": TierLimits(watchlist_max=25,  queries_per_day=100,    backtest_per_day=50,    screener_refresh_seconds=300),
    "pro":      TierLimits(watchlist_max=100, queries_per_day=1000,   backtest_per_day=200,   screener_refresh_seconds=60),
    "api":      TierLimits(watchlist_max=1000, queries_per_day=100000, backtest_per_day=10000, screener_refresh_seconds=0),
}

STRIPE_PRICES: dict[str, dict[str, str]] = {
    "investor": {
        "INR": os.environ.get("STRIPE_PRICE_INVESTOR_INR", ""),
        "USD": os.environ.get("STRIPE_PRICE_INVESTOR_USD", ""),
    },
    "pro": {
        "INR": os.environ.get("STRIPE_PRICE_PRO_INR", ""),
        "USD": os.environ.get("STRIPE_PRICE_PRO_USD", ""),
    },
    "api": {
        "INR": os.environ.get("STRIPE_PRICE_API_INR", ""),
        "USD": os.environ.get("STRIPE_PRICE_API_USD", ""),
    },
}

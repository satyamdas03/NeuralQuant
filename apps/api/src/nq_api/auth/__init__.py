"""Auth module — Supabase JWT verification + current user deps."""
from .models import User, Tier
from .jwt_verify import verify_supabase_jwt, JWTVerificationError
from .deps import get_current_user, get_current_user_optional

__all__ = [
    "User",
    "Tier",
    "verify_supabase_jwt",
    "JWTVerificationError",
    "get_current_user",
    "get_current_user_optional",
]

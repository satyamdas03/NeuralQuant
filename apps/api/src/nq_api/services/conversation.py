"""Conversation history management -- persist and load from Supabase."""
import logging

logger = logging.getLogger(__name__)


def _save_conversation_turn(user_id: str | None, session_key: str, role: str, content: str,
                            ticker: str | None = None, market: str = "US") -> None:
    """Persist a conversation turn to Supabase for multi-session memory."""
    if not user_id or not session_key:
        return
    try:
        from nq_api.cache.score_cache import _supabase_rest
        _supabase_rest("conversations", method="POST", body=[{
            "user_id": user_id,
            "session_key": session_key,
            "role": role,
            "content": content[:5000],  # truncate long messages
            "ticker": ticker,
            "market": market,
        }])
    except Exception as e:
        logger.debug("Non-critical enrichment failed: %s", e)
        pass  # Best-effort -- never block the main query flow


def _load_conversation_history(user_id: str | None, session_key: str, limit: int = 20) -> list[dict]:
    """Load recent conversation turns for multi-session memory."""
    if not user_id or not session_key:
        return []
    try:
        from nq_api.cache.score_cache import _supabase_rest
        data = _supabase_rest("conversations", method="GET", query={
            "select": "role,content,created_at",
            "user_id": f"eq.{user_id}",
            "session_key": f"eq.{session_key}",
            "order": "created_at.desc",
            "limit": str(limit),
        })
        if isinstance(data, list) and data:
            # Return in chronological order
            data.reverse()
            return data
    except Exception:
        pass
    return []

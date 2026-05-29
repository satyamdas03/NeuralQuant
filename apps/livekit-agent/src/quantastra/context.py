"""Build runtime context injected at conversation start for QuantAstra agent."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

log = logging.getLogger(__name__)


async def _fetch_user_name(user_id: str) -> str | None:
    """Fetch the user's display name from Supabase users table."""
    try:
        from nq_api.cache.score_cache import _supabase_rest

        result = _supabase_rest(
            f"users?id=eq.{user_id}&select=name,email",
            method="GET",
        )
        if isinstance(result, list) and result:
            name = result[0].get("name")
            if name:
                return name
            email = result[0].get("email", "")
            if "@" in email:
                return email.split("@")[0]
    except Exception:
        log.warning("Failed to fetch user name for %s", user_id)
    return None


async def build_personalized_greeting(user_id: str) -> str:
    """Build a personalized greeting for the user based on profile and session history.

    Returns a greeting string for the agent's first spoken utterance.
    """
    name = await _fetch_user_name(user_id)
    last_summary = await _fetch_last_session_summary(user_id)

    if name and last_summary:
        return (
            f"Hey {name}, welcome back. In our last session we talked about "
            f"{last_summary} What's on your mind today?"
        )

    if name:
        return (
            f"Hey {name}, I'm QuantAstra, your portfolio manager at QuantAlpha. "
            "I've got live markets, AI research, and your portfolio pulled up. "
            "What's on your mind today?"
        )

    from quantastra.persona import INITIAL_GREETING
    return INITIAL_GREETING


async def _fetch_last_session_summary(user_id: str) -> str | None:
    """Fetch the most recent session summary for a user from Supabase."""
    try:
        from nq_api.cache.score_cache import _supabase_rest

        result = _supabase_rest(
            f"session_reports?user_id=eq.{user_id}&select=summary,generated_at&order=generated_at.desc&limit=1",
            method="GET",
        )
        if isinstance(result, list) and result:
            return result[0].get("summary")
    except Exception:
        log.warning("Failed to fetch last session summary for user %s", user_id)
    return None


async def summarize_and_store_session(user_id: str, turns: list[dict]) -> None:
    """Summarize conversation turns with Claude and store in Supabase session_reports."""
    if not turns:
        return

    conv_text = "\n".join(
        f"{'User' if t['role'] == 'user' else 'Agent'}{' [' + t.get('tool', '') + ']' if t.get('tool') else ''}: {t['text']}"
        for t in turns
    )

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        log.warning("No ANTHROPIC_API_KEY — skipping session memory summarization")
        return

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            temperature=0.5,
            system="Summarize this QuantAstra voice conversation in 2-3 sentences. Focus on: stocks discussed, questions asked, key conclusions. Be specific, concise. Write in past tense. Example: 'User asked about NVDA valuation after earnings. Agent ran PARA-DEBATE showing mixed signals — Bull case $175, Bear case $130. Recommended waiting for pullback to $140.'",
            messages=[{"role": "user", "content": f"Summarize this voice conversation:\n\n{conv_text}"}],
        )

        summary = ""
        if hasattr(resp, "content") and resp.content:
            for block in resp.content:
                if hasattr(block, "text"):
                    summary += block.text
        summary = summary.strip()

        if not summary:
            return

        from nq_api.cache.score_cache import _supabase_rest

        # Create a lightweight user_sessions row so session_reports FK is satisfied
        session_id = _new_uuid()
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            _supabase_rest(
                "user_sessions",
                method="POST",
                body=[{
                    "id": session_id,
                    "user_id": user_id,
                    "started_at": now_iso,
                    "ended_at": now_iso,
                    "duration_seconds": 0,
                    "is_guest": False,
                    "metadata": {"source": "quantastra_voice"},
                }],
            )
        except Exception:
            log.warning("Failed to create user_sessions row for %s — skipping", user_id)
            return

        _supabase_rest(
            "session_reports",
            method="POST",
            body=[{
                "user_id": user_id,
                "session_id": session_id,
                "summary": summary,
                "report_text": conv_text,
                "generated_at": now_iso,
            }],
        )
        log.info("Session memory stored for user %s: %s", user_id, summary[:100])
    except Exception:
        log.exception("Failed to summarize and store session for user %s", user_id)


def _new_uuid() -> str:
    import uuid
    return str(uuid.uuid4())


async def build_greeting_context(user_id: str | None) -> str:
    """Build the initial market + portfolio context block injected with the system prompt.

    Called once when a new LiveKit room is created. Returns a text block
    with live macro data and top AI scores.
    """
    parts: list[str] = []

    # ── Macro context ──────────────────────────────────────────────────────
    try:
        from nq_api.data_builder import fetch_real_macro

        macro = fetch_real_macro()
        if macro is not None:
            parts.append("CURRENT MARKET CONTEXT [VERIFIED live from FMP/yfinance]:")
            vix = getattr(macro, "vix", None)
            if vix is not None:
                parts.append(f"  VIX: {vix:.1f}")
            spx_ret = getattr(macro, "spx_return_1m", None)
            spx_vs_ma = getattr(macro, "spx_vs_200ma", None)
            if spx_ret is not None:
                parts.append(
                    f"  S&P 500: 1mo return {spx_ret:+.1%}"
                    + (f", vs 200MA {spx_vs_ma:+.1%}" if spx_vs_ma is not None else "")
                )
            yield_10y = getattr(macro, "yield_10y", None)
            if yield_10y is not None:
                parts.append(f"  10Y Treasury Yield: {yield_10y:.2f}%")
            fed_funds = getattr(macro, "fed_funds_rate", None)
            if fed_funds is not None:
                parts.append(f"  Fed Funds Rate: {fed_funds:.2f}%")
            hy_spread = getattr(macro, "hy_spread_oas", None)
            if hy_spread is not None:
                parts.append(f"  High-Yield Spread: {hy_spread:.0f} bps")
            cpi = getattr(macro, "cpi_yoy", None)
            if cpi is not None:
                parts.append(f"  CPI YoY: {cpi:.1f}%")
            ism = getattr(macro, "ism_pmi", None)
            if ism is not None:
                parts.append(f"  ISM PMI: {ism:.1f}")
            spread_2s10s = getattr(macro, "yield_spread_2y10y", None)
            if spread_2s10s is not None:
                parts.append(f"  2s10s Yield Spread: {spread_2s10s:.2f}%")
    except Exception as exc:
        log.warning("Macro context build failed: %s", exc)

    # ── Top AI scores ──────────────────────────────────────────────────────
    try:
        from nq_api.cache.score_cache import read_top

        us_top = read_top("US", 5)
        if us_top:
            parts.append(
                "\nTOP US AI SCORES [VERIFIED]: "
                + ", ".join(f"{s['ticker']}={s['score_1_10']}/10" for s in us_top)
            )
        in_top = read_top("IN", 5)
        if in_top:
            parts.append(
                "TOP INDIA AI SCORES [VERIFIED]: "
                + ", ".join(f"{s['ticker']}={s['score_1_10']}/10" for s in in_top)
            )
    except Exception as exc:
        log.warning("Score context build failed: %s", exc)

    # ── Previous session context ────────────────────────────────────────────
    if user_id and user_id != "anonymous":
        try:
            last_summary = await _fetch_last_session_summary(user_id)
            if last_summary:
                parts.append(
                    "\nLAST SESSION RECAP [from your previous conversation with this user]: "
                    + last_summary
                )
        except Exception as exc:
            log.warning("Session memory fetch failed: %s", exc)

    # ── Portfolio holdings — loaded via tool call, not at startup ──────────
    # Portfolio data requires an authenticated Supabase query; the agent
    # loads it on-demand via the lookup_portfolio tool.

    return "\n".join(parts) if parts else ""

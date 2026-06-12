"""Pure logic for the Veronica companion agent — no livekit imports.

Kept separate from veronica_agent.py so unit tests don't need the
livekit-agents dependency tree.
"""

from __future__ import annotations


def agent_kind_for_room(room_name: str | None) -> str:
    """Route a LiveKit room to its persona. Unknown rooms keep the
    historical QuantAstra behavior."""
    if room_name and room_name.startswith("veronica-"):
        return "veronica"
    return "quantastra"


def parse_page_context(msg) -> dict | None:
    """Validate and normalize a page_context data-channel message.

    Returns None for anything that isn't a page_context dict.
    """
    if not isinstance(msg, dict) or msg.get("type") != "page_context":
        return None
    route = msg.get("route")
    if not isinstance(route, str) or not route:
        return None
    ticker = msg.get("ticker")
    return {
        "route": route,
        "page_type": msg.get("pageType") or "page",
        "ticker": ticker if isinstance(ticker, str) and ticker else None,
        "narrate": bool(msg.get("narrate", False)),
    }


def build_narration_instructions(ctx: dict) -> str:
    """LLM instructions for a short spoken page summary."""
    where = f"the {ctx['page_type'].replace('_', ' ')} page ({ctx['route']})"
    subject = f" for {ctx['ticker']}" if ctx.get("ticker") else ""
    return (
        f"The user just opened {where}{subject}. "
        "Give a spoken summary of what they're looking at and what it means — "
        "10 to 15 seconds maximum when read aloud. "
        f"{'Use your tools to pull live data on ' + ctx['ticker'] + ' if helpful, but do not let tool calls delay you more than a few seconds — speak with what you have. ' if ctx.get('ticker') else ''}"
        "No markdown, no lists, flowing sentences only. Do not greet them again. "
        "End by inviting a question only if natural — never robotic."
    )


def build_veronica_greeting(name: str | None) -> str:
    """First spoken utterance after the user enables Veronica."""
    if name:
        return (
            f"Hi {name}, Veronica here. I'm with you on every page now — "
            "just speak whenever you have a question. "
            "Want me to walk you through what you're looking at?"
        )
    return (
        "Hi, I'm Veronica — your companion here at QuantAlpha. "
        "I'm with you on every page. Just speak whenever something "
        "catches your eye and I'll explain it."
    )

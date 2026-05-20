"""QuantAstra — LiveKit Voice Agent entry point.

Long-running worker that connects to LiveKit Cloud over WebSocket,
joins rooms matching quantastra-*, and runs the cascaded
STT→LLM→TTS pipeline: Deepgram → Claude Sonnet 4.6 → ElevenLabs.
"""

from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.plugins import anthropic as lk_anthropic
from livekit.plugins import deepgram
from livekit.plugins import elevenlabs

from quantastra.context import build_greeting_context
from quantastra.persona import INITIAL_GREETING, SYSTEM_PROMPT
from quantastra.tools.macro_tools import MacroToolsMixin
from quantastra.tools.market_tools import MarketToolsMixin
from quantastra.tools.portfolio_tools import PortfolioToolsMixin
from quantastra.tools.research_tools import ResearchToolsMixin
from quantastra.tools.screener_tools import ScreenerToolsMixin

load_dotenv()

log = logging.getLogger("quantastra")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))


class QuantAstraAgent(
    MarketToolsMixin,
    PortfolioToolsMixin,
    ScreenerToolsMixin,
    ResearchToolsMixin,
    MacroToolsMixin,
    Agent,
):
    """QuantAstra — AI Portfolio Manager with 15 function-calling tools."""

    def __init__(self, user_id: str, context: str):
        full_instructions = SYSTEM_PROMPT
        if context:
            full_instructions += f"\n\n=== LIVE MARKET DATA ===\n{context}"
        super().__init__(
            instructions=full_instructions,
            stt=deepgram.STT(
                model="nova-2-general",
                api_key=os.getenv("DEEPGRAM_API_KEY"),
            ),
            llm=lk_anthropic.LLM(
                model="claude-sonnet-4-6",
                temperature=0.7,
                max_tokens=2048,
                api_key=os.getenv("ANTHROPIC_API_KEY"),
            ),
            tts=elevenlabs.TTS(
                model="eleven_turbo_v2_5",
                voice_id="EXAVITQu4vr4xnSDxMaL",
                api_key=os.getenv("ELEVENLABS_API_KEY"),
            ),
            allow_interruptions=True,
        )
        self.user_id = user_id


async def entrypoint(ctx: JobContext):
    """LiveKit worker entrypoint — called when agent joins a room."""
    log.info("QuantAstra agent joining room: %s", ctx.room.name)

    user_id = "anonymous"
    room_name = ctx.room.name or ""
    if room_name.startswith("quantastra-"):
        extracted = room_name[len("quantastra-"):]
        if extracted:
            user_id = extracted

    try:
        greeting_text = await build_greeting_context(user_id)
    except Exception:
        log.exception("Failed to build greeting context")
        greeting_text = ""

    agent = QuantAstraAgent(user_id, greeting_text)

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    session = AgentSession()
    await session.start(agent=agent, room=ctx.room)

    session.say(INITIAL_GREETING)

    log.info("QuantAstra agent ready in room: %s", ctx.room.name)

    async def _on_shutdown(reason: str = "") -> None:
        log.info("Agent shutting down: %s", reason)
        shutdown_event.set()

    shutdown_event = asyncio.Event()
    ctx.add_shutdown_callback(_on_shutdown)
    await shutdown_event.wait()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))

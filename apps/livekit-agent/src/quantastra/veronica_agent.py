"""VERONICA — ambient voice companion. Runs in the same LiveKit worker
as QuantAstra; the entrypoint routes veronica-* rooms here."""

from __future__ import annotations

import asyncio
import json
import logging
import os

from livekit.agents import Agent, AgentSession, AutoSubscribe, JobContext, ModelSettings
from livekit.agents.types import APIConnectOptions
from livekit.agents.voice.agent_session import SessionConnectOptions
from livekit.plugins import anthropic as lk_anthropic
from livekit.plugins import deepgram, elevenlabs
from livekit.rtc import LocalParticipant

from quantastra.context import _fetch_user_name, summarize_and_store_session
from quantastra.tools.macro_tools import MacroToolsMixin
from quantastra.tools.market_tools import MarketToolsMixin
from quantastra.tools.portfolio_tools import PortfolioToolsMixin
from quantastra.tools.research_tools import ResearchToolsMixin
from quantastra.tools.screener_tools import ScreenerToolsMixin
from quantastra.veronica_logic import (
    build_narration_instructions,
    build_veronica_greeting,
    parse_page_context,
)
from quantastra.veronica_persona import VERONICA_SYSTEM_PROMPT

log = logging.getLogger("veronica")

# ElevenLabs "Charlotte" — distinct from Astra's voice. Override per-env.
VERONICA_VOICE_ID = os.getenv("VERONICA_VOICE_ID", "XB0fDUnXU5powFXDhCwa")


async def _publish(participant: LocalParticipant | None, msg: dict) -> None:
    """Publish a JSON message to the frontend via LiveKit data channel."""
    if participant is None:
        return
    try:
        await participant.publish_data(
            json.dumps(msg), reliable=True, topic="veronica"
        )
    except Exception:
        log.debug("Failed to publish data to frontend", exc_info=True)


class VeronicaAgent(
    MarketToolsMixin,
    PortfolioToolsMixin,
    ScreenerToolsMixin,
    ResearchToolsMixin,
    MacroToolsMixin,
    Agent,
):
    """Ambient companion — QuantAstra's tool mixins minus whiteboard/upload."""

    def __init__(self, user_id: str):
        super().__init__(
            instructions=VERONICA_SYSTEM_PROMPT,
            stt=deepgram.STT(
                model="nova-2-general",
                api_key=os.getenv("DEEPGRAM_API_KEY"),
            ),
            llm=lk_anthropic.LLM(
                model="claude-sonnet-4-6",
                temperature=0.6,
                max_tokens=1024,
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                # Same >16-union API limit as QuantAstra (agent.py:108)
                _strict_tool_schema=False,
            ),
            tts=elevenlabs.TTS(
                model="eleven_turbo_v2_5",
                voice_id=VERONICA_VOICE_ID,
                api_key=os.getenv("ELEVENLABS_API_KEY"),
            ),
            allow_interruptions=True,
        )
        self._user_id = user_id
        self._participant: LocalParticipant | None = None
        self._conversation_turns: list[dict] = []
        self._current_agent_text: str = ""
        self._latest_page: dict | None = None

    async def transcription_node(self, text, model_settings: ModelSettings):
        """Stream agent speech text to the frontend alongside TTS audio."""
        self._current_agent_text = ""
        async for chunk in text:
            chunk_str = chunk if isinstance(chunk, str) else chunk.text
            if chunk_str.strip():
                self._current_agent_text += chunk_str
                await _publish(self._participant, {
                    "type": "agent_transcript",
                    "text": chunk_str,
                    "final": False,
                })
            yield chunk
        if self._current_agent_text.strip():
            self._conversation_turns.append({
                "role": "agent",
                "text": self._current_agent_text.strip(),
            })
            self._current_agent_text = ""
        await _publish(self._participant, {
            "type": "agent_transcript", "text": "", "final": True,
        })


async def run_veronica(ctx: JobContext) -> None:
    """Entrypoint body for veronica-* rooms."""
    room_name = ctx.room.name or ""
    user_id = room_name[len("veronica-"):] or "unknown"
    log.info("Veronica joining room: %s (user %s)", room_name, user_id)

    agent = VeronicaAgent(user_id)

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    session = AgentSession(
        conn_options=SessionConnectOptions(
            llm_conn_options=APIConnectOptions(timeout=60.0),
        )
    )

    @ctx.room.on("data_received")
    def _on_data_received(data_packet):
        topic = getattr(data_packet, "topic", None)
        if topic not in (None, "veronica"):
            return
        raw = data_packet.data if hasattr(data_packet, "data") else data_packet
        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            msg = json.loads(raw) if isinstance(raw, str) else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        page = parse_page_context(msg)
        if page is None:
            return
        agent._latest_page = page
        asyncio.ensure_future(_handle_page(agent, session, page))

    async def _handle_page(agent: VeronicaAgent, session: AgentSession, page: dict) -> None:
        # Ground Q&A first so narration sees the [PAGE] note, then speak.
        await _note_page(agent, page)
        if page["narrate"]:
            await _narrate(session, page)

    async def _note_page(agent: VeronicaAgent, page: dict) -> None:
        try:
            chat_ctx = agent.chat_ctx.copy()
            chat_ctx.add_message(
                role="system",
                content=f"[PAGE] User is now viewing {page['page_type']} "
                        f"({page['route']})"
                        + (f", ticker {page['ticker']}" if page["ticker"] else "")
                        + ".",
            )
            await agent.update_chat_ctx(chat_ctx)
        except Exception:
            # Grounding is best-effort; _latest_page still set.
            log.debug("update_chat_ctx failed", exc_info=True)

    async def _narrate(session: AgentSession, page: dict) -> None:
        try:
            session.interrupt()  # new page cuts any in-flight speech
        except Exception:
            pass
        try:
            session.generate_reply(
                instructions=build_narration_instructions(page)
            )
        except Exception:
            # Narration must never take the session down.
            log.exception("Narration failed for %s", page.get("route"))

    await session.start(agent=agent, room=ctx.room)

    participant = ctx.room.local_participant
    agent._participant = participant

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev):
        asyncio.ensure_future(_publish(participant, {
            "type": "agent_state",
            "state": ev.new_state if hasattr(ev, "new_state") else str(ev),
        }))

    @session.on("user_input_transcribed")
    def _on_user_transcribed(ev):
        text = ev.transcript if hasattr(ev, "transcript") else str(ev)
        is_final = ev.is_final if hasattr(ev, "is_final") else True
        if is_final and text.strip():
            agent._conversation_turns.append({"role": "user", "text": text.strip()})
        asyncio.ensure_future(_publish(participant, {
            "type": "user_transcript", "text": text, "is_final": is_final,
        }))

    try:
        name = await _fetch_user_name(user_id)
    except Exception:
        name = None
    session.say(build_veronica_greeting(name))

    log.info("Veronica ready in room: %s", room_name)

    shutdown_event = asyncio.Event()

    async def _on_shutdown(reason: str = "") -> None:
        log.info("Veronica shutting down: %s", reason)
        if agent._conversation_turns:
            try:
                await summarize_and_store_session(user_id, agent._conversation_turns)
            except Exception:
                log.exception("Failed to store Veronica session memory")
        shutdown_event.set()

    ctx.add_shutdown_callback(_on_shutdown)
    await shutdown_event.wait()

"""QuantAstra — LiveKit Voice Agent entry point.

Long-running worker that connects to LiveKit Cloud over WebSocket,
joins rooms matching quantastra-*, and runs the cascaded
STT→LLM→TTS pipeline: Deepgram → Claude Sonnet 4.6 → ElevenLabs.

Publishes agent state, transcripts, and tool results to frontend
via LiveKit data channel (topic: "quantastra").
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    ModelSettings,
    WorkerOptions,
    cli,
)
from livekit.plugins import anthropic as lk_anthropic
from livekit.plugins import sarvam
from livekit.rtc import LocalParticipant

from quantastra.context import build_greeting_context
from quantastra.persona import INITIAL_GREETING, SYSTEM_PROMPT
from quantastra.tools.macro_tools import MacroToolsMixin
from quantastra.tools.market_tools import MarketToolsMixin
from quantastra.tools.portfolio_tools import PortfolioToolsMixin
from quantastra.tools.research_tools import ResearchToolsMixin
from quantastra.tools.screener_tools import ScreenerToolsMixin
from quantastra.multilingual_tts import MultilingualSarvamTTS
from quantastra.tools.upload_tools import UploadToolsMixin
from quantastra.tools.whiteboard_tools import WhiteboardToolsMixin

load_dotenv()

log = logging.getLogger("quantastra")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
log.info("quantastra-agent worker starting — LiveKit URL: %s", os.getenv("LIVEKIT_URL", "not set"))


async def _publish(participant: LocalParticipant | None, msg: dict) -> None:
    """Publish a JSON message to the frontend via LiveKit data channel."""
    if participant is None:
        return
    try:
        payload = json.dumps(msg)
        await participant.publish_data(payload, reliable=True, topic="quantastra")
    except Exception:
        log.debug("Failed to publish data to frontend", exc_info=True)


class QuantAstraAgent(
    MarketToolsMixin,
    PortfolioToolsMixin,
    ScreenerToolsMixin,
    ResearchToolsMixin,
    MacroToolsMixin,
    WhiteboardToolsMixin,
    UploadToolsMixin,
    Agent,
):
    """QuantAstra — AI Portfolio Manager with 15 function-calling tools.

    Overrides transcription_node() to stream agent speech text to the
    frontend in real-time alongside TTS audio playback.
    """

    def __init__(self, user_id: str, context: str):
        full_instructions = SYSTEM_PROMPT
        if context:
            full_instructions += f"\n\n=== LIVE MARKET DATA ===\n{context}"
        super().__init__(
            instructions=full_instructions,
            stt=sarvam.STT(
                model="saaras:v3",
                mode="codemix",
            ),
            llm=lk_anthropic.LLM(
                model="claude-sonnet-4-6",
                temperature=0.7,
                max_tokens=2048,
                api_key=os.getenv("ANTHROPIC_API_KEY"),
            ),
            tts=MultilingualSarvamTTS(
                model="bulbul:v3",
                speaker="priya",
                pace=1.0,
                temperature=0.6,
            ),
            allow_interruptions=True,
        )
        self._user_id = user_id
        self._participant: LocalParticipant | None = None

    async def transcription_node(
        self, text, model_settings: ModelSettings
    ):
        """Override: pass text through to TTS unchanged while publishing
        each chunk to the frontend as a live transcript."""
        async for chunk in text:
            chunk_str = chunk if isinstance(chunk, str) else chunk.text
            if chunk_str.strip():
                await _publish(self._participant, {
                    "type": "agent_transcript",
                    "text": chunk_str,
                    "final": False,
                })
            yield chunk

        # Signal end of this speech segment
        await _publish(self._participant, {
            "type": "agent_transcript",
            "text": "",
            "final": True,
        })


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

    # ── File upload data channel listener ────────────────────────────────
    @ctx.room.on("data_received")
    def _on_data_received(data_packet):
        # LiveKit passes a DataPacket object with .data (bytes), .topic, .participant
        raw = data_packet.data if hasattr(data_packet, "data") else data_packet
        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            msg = json.loads(raw) if isinstance(raw, str) else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        if msg.get("type") == "file_upload":
            file_name = msg.get("file_name", "unknown")
            mime_type = msg.get("mime_type", "application/octet-stream")
            data_b64 = msg.get("data_b64", "")
            size = msg.get("size", 0)
            agent._add_upload(file_name, mime_type, data_b64, size)
            log.info("Received file upload: %s (%s, %d bytes)", file_name, mime_type, size)

    await session.start(agent=agent, room=ctx.room)

    # ── Wire up data channel publishing ──────────────────────────────────
    participant = ctx.room.local_participant
    agent._participant = participant

    # Publish agent state changes to frontend
    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev):
        asyncio.ensure_future(_publish(participant, {
            "type": "agent_state",
            "state": ev.new_state if hasattr(ev, "new_state") else str(ev),
        }))

    # Publish user transcriptions to frontend
    @session.on("user_input_transcribed")
    def _on_user_transcribed(ev):
        asyncio.ensure_future(_publish(participant, {
            "type": "user_transcript",
            "text": ev.transcript if hasattr(ev, "transcript") else str(ev),
            "is_final": ev.is_final if hasattr(ev, "is_final") else True,
        }))

    # Publish tool call results to frontend
    @session.on("function_tools_executed")
    def _on_tools_executed(ev):
        calls = ev.function_calls if hasattr(ev, "function_calls") else []
        outputs = ev.function_call_outputs if hasattr(ev, "function_call_outputs") else []
        tool_results = []
        for call, output in zip(calls, outputs):
            name = call.name if hasattr(call, "name") else str(call)
            try:
                parsed = json.loads(output) if isinstance(output, str) else output
            except (json.JSONDecodeError, TypeError):
                parsed = str(output)[:500]
            tool_results.append({"tool": name, "result": parsed})
        if tool_results:
            asyncio.ensure_future(_publish(participant, {
                "type": "tool_results",
                "data": tool_results,
            }))

    session.say(INITIAL_GREETING)

    log.info("QuantAstra agent ready in room: %s", ctx.room.name)

    async def _on_shutdown(reason: str = "") -> None:
        log.info("Agent shutting down: %s", reason)
        shutdown_event.set()

    shutdown_event = asyncio.Event()
    ctx.add_shutdown_callback(_on_shutdown)
    await shutdown_event.wait()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="quantastra",
        ws_url=os.getenv("LIVEKIT_URL"),
        api_key=os.getenv("LIVEKIT_API_KEY"),
        api_secret=os.getenv("LIVEKIT_API_SECRET"),
    ))

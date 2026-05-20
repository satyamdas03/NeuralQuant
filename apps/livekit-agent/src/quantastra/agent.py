"""QuantAstra — LiveKit VoicePipelineAgent entry point.

Long-running worker that connects to LiveKit Cloud over WebSocket,
joins rooms matching quantastra-*, and runs the cascaded
STT→LLM→TTS pipeline: Deepgram → Claude Sonnet 4.6 → ElevenLabs.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, WorkerType
from livekit.agents.llm import FunctionContext
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import anthropic as lk_anthropic
from livekit.plugins import deepgram
from livekit.plugins import elevenlabs

from quantastra.context import build_greeting_context
from quantastra.dispatcher import dispatch
from quantastra.persona import SYSTEM_PROMPT
from quantastra.tools import register_all_tools

load_dotenv()

log = logging.getLogger("quantastra")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))


async def entrypoint(ctx: JobContext):
    """LiveKit worker entrypoint — called when agent joins a room."""
    log.info("QuantAstra agent joining room: %s", ctx.room.name)

    # Extract user_id from room name: quantastra-{user_id}
    user_id = None
    room_name = ctx.room.name or ""
    if room_name.startswith("quantastra-"):
        user_id = room_name[len("quantastra-"):] or None
    if not user_id:
        user_id = "anonymous"

    # Build live market + portfolio context
    greeting_text = await build_greeting_context(user_id)

    # Build the initial chat context
    full_context = SYSTEM_PROMPT
    if greeting_text:
        full_context += f"\n\n=== LIVE MARKET DATA ===\n{greeting_text}"

    # Assemble the agent pipeline
    agent = VoicePipelineAgent(
        stt=deepgram.STT(model="nova-2-general"),
        llm=lk_anthropic.LLM(
            model="claude-sonnet-4-6",
            temperature=0.7,
            max_tokens=2048,
        ),
        tts=elevenlabs.TTS(
            model_id="eleven_turbo_v2_5",
            voice_id="EXAVITQu4vr4xnSDxMaL",
        ),
        chat_ctx=llm.ChatContext().append(
            text=full_context,
            role="system",
        ),
        fnc_ctx=register_all_tools(),
        allow_interruptions=True,
    )

    # Run the agent until the room disconnects
    agent.start(ctx.room)

    # Greet the user — dispatcher handles participant join/leave
    await dispatch(ctx, agent, user_id)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            worker_type=WorkerType.ROOM,
            auto_subscribe=AutoSubscribe.AUDIO_ONLY,
        )
    )

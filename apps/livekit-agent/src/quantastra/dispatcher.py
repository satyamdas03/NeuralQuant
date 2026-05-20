"""Room lifecycle management for QuantAstra agent.

Handles participant join/leave events and dispatches the initial
greeting message when the first participant (the user) joins.
"""

from __future__ import annotations

import logging

from livekit.agents import JobContext
from livekit.agents.pipeline import VoicePipelineAgent

from quantastra.persona import INITIAL_GREETING

log = logging.getLogger(__name__)


async def dispatch(ctx: JobContext, agent: VoicePipelineAgent, user_id: str):
    """Handle room lifecycle — greet user on join, log on leave."""

    @ctx.room.on("participant_connected")
    def _on_participant_joined(participant):
        """Greet the user when they first join the room."""
        identity = participant.identity or "anonymous"
        log.info("Participant joined room %s: %s", ctx.room.name, identity)
        # Only greet the first human participant (the user), not other agents
        if identity != "quantastra" and not identity.startswith("agent-"):
            agent.say(INITIAL_GREETING)

    @ctx.room.on("participant_disconnected")
    def _on_participant_left(participant):
        """Log when a participant leaves."""
        identity = participant.identity or "anonymous"
        log.info("Participant left room %s: %s", ctx.room.name, identity)

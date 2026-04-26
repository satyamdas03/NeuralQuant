"""Slack Bolt app with Socket Mode — integrates into FastAPI lifespan.

Graceful degradation: if SLACK_BOT_TOKEN or SLACK_APP_TOKEN are not set,
the system logs a warning and disables Slack integration (no crash).
"""

from __future__ import annotations

import asyncio
import logging
import os

from nq_api.slack.config import SLACK_BOT_TOKEN, SLACK_APP_TOKEN

logger = logging.getLogger(__name__)

_slack_app = None
_socket_handler = None


def _create_slack_app():
    """Create the Slack Bolt AsyncApp if tokens are configured."""
    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        logger.info(
            "SLACK_BOT_TOKEN or SLACK_APP_TOKEN not set — "
            "Slack agent system disabled"
        )
        return None

    try:
        from slack_bolt.async_app import AsyncApp
    except ImportError:
        logger.warning("slack-bolt not installed — Slack agent system disabled")
        return None

    app = AsyncApp(token=SLACK_BOT_TOKEN)

    @app.event("message")
    async def handle_message(event, say):
        """Route incoming Slack messages to the correct agent."""
        # Ignore bot's own messages
        if event.get("bot_id"):
            return

        channel = event.get("channel", "")
        user_id = event.get("user", "")
        text = event.get("text", "").strip()

        if not text:
            return

        # Strip @mention if present
        if text.startswith("<@"):
            import re
            text = re.sub(r"^<@[A-Z0-9]+>\s*", "", text).strip()

        thread_ts = event.get("thread_ts")
        context = {
            "channel": channel,
            "thread_ts": thread_ts,
            "event_ts": event.get("ts", ""),
        }

        from nq_api.slack.dispatcher import dispatch_message

        try:
            result = await dispatch_message(channel, user_id, text, context)
        except Exception as exc:
            logger.exception("Agent dispatch failed for channel %s", channel)
            result = {
                "response": f"Agent error: {str(exc)[:200]}",
                "needs_approval": False,
            }

        if result and result.get("response"):
            reply_kwargs = {"text": result["response"]}
            if thread_ts:
                reply_kwargs["thread_ts"] = thread_ts
            await say(**reply_kwargs)

    @app.event("app_mention")
    async def handle_mention(event, say):
        """Handle @NQ mentions in any channel — same routing."""
        await handle_message(event, say)

    return app


async def start_slack_handler() -> None:
    """Start the Socket Mode handler as a background task.

    Called from FastAPI lifespan startup.
    """
    global _slack_app, _socket_handler

    _slack_app = _create_slack_app()
    if not _slack_app:
        return

    # Initialize agents (lazy load)
    from nq_api.slack.dispatcher import _init_agents
    _init_agents()

    try:
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    except ImportError:
        logger.warning("slack-bolt socket mode not available — Slack disabled")
        return

    handler = AsyncSocketModeHandler(_slack_app, SLACK_APP_TOKEN)

    logger.info("Starting Slack Socket Mode handler...")
    # Start the handler in the background — it maintains the WebSocket
    task = asyncio.create_task(handler.connect_async())
    _socket_handler = handler
    logger.info("Slack Socket Mode handler started")


async def stop_slack_handler() -> None:
    """Gracefully shut down the Slack handler.

    Called from FastAPI lifespan shutdown.
    """
    global _socket_handler
    if _socket_handler:
        logger.info("Stopping Slack Socket Mode handler...")
        try:
            await _socket_handler.disconnect()
        except Exception as exc:
            logger.warning("Error stopping Slack handler: %s", exc)
        _socket_handler = None
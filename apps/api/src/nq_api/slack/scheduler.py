"""Lightweight in-process scheduler for daily agent tasks.

Uses asyncio tasks with sleep loops — no Celery/Redis required.
Runs as background tasks in the FastAPI event loop.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_scheduled_tasks: list[asyncio.Task] = []


async def start_scheduler() -> None:
    """Start all scheduled agent tasks.

    Called from FastAPI lifespan startup, after Slack handler starts.
    """
    task_defs = [
        (_india_morning_brief, "India Morning Brief", 3, 30),   # 9:00 AM IST = 3:30 UTC
        (_us_morning_brief, "US Morning Brief", 14, 30),        # 9:30 AM EST = 14:30 UTC
        (_daily_ops_check, "Daily Ops Check", 3, 0),              # 8:30 AM IST = 3:00 UTC
        (_nightly_score_verify, "Nightly Score Verify", 5, 0),   # After GHA nightly at 2:00 UTC
    ]

    for coro_fn, name, hour_utc, minute_utc in task_defs:
        t = asyncio.create_task(
            _run_daily(coro_fn, name, hour_utc, minute_utc)
        )
        _scheduled_tasks.append(t)

    logger.info("Scheduler started with %d tasks", len(task_defs))


async def stop_scheduler() -> None:
    """Cancel all scheduled tasks."""
    for t in _scheduled_tasks:
        t.cancel()
    _scheduled_tasks.clear()
    logger.info("Scheduler stopped")


async def _run_daily(coro_fn, name: str, hour_utc: int, minute_utc: int) -> None:
    """Run a coroutine once per day at the specified UTC time."""
    while True:
        now = datetime.now(timezone.utc)
        target = now.replace(hour=hour_utc, minute=minute_utc, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        delay = (target - now).total_seconds()
        logger.info("Scheduler: %s next run in %d seconds", name, int(delay))
        await asyncio.sleep(delay)
        try:
            await coro_fn()
        except Exception as exc:
            logger.exception("Scheduled task %s failed: %s", name, exc)


async def _post_to_slack(channel_name: str, text: str) -> None:
    """Post a message to a Slack channel via the Slack app client."""
    if not text:
        return

    from nq_api.slack.app import _slack_app
    from nq_api.slack.config import CHANNEL_MAP

    if not _slack_app:
        logger.warning("Slack app not initialized, cannot post to %s", channel_name)
        return

    channel_id = CHANNEL_MAP.get(channel_name)
    if not channel_id:
        logger.warning("No Slack channel ID mapped for %s", channel_name)
        return

    try:
        await _slack_app.client.chat_postMessage(channel=channel_id, text=text)
    except Exception as exc:
        logger.error("Failed to post to %s: %s", channel_name, exc)


async def _india_morning_brief() -> None:
    """NQ-INTEL: India market morning brief posted to #nq-intel."""
    from nq_api.slack.dispatcher import get_agent_for_channel

    agent = get_agent_for_channel("nq-intel")
    if agent:
        result = await agent.run(
            "Generate India market morning brief for today. "
            "Include: Nifty 50 levels, FII/DII flows, key sector moves, top gainers/losers.",
            {"channel": "nq-intel", "scheduled": True},
        )
        await _post_to_slack("nq-intel", result.get("response", ""))


async def _us_morning_brief() -> None:
    """NQ-INTEL: US market morning brief posted to #nq-intel."""
    from nq_api.slack.dispatcher import get_agent_for_channel

    agent = get_agent_for_channel("nq-intel")
    if agent:
        result = await agent.run(
            "Generate US market morning brief for today. "
            "Include: S&P 500 levels, VIX, Fed calendar, earnings, key sectors.",
            {"channel": "nq-intel", "scheduled": True},
        )
        await _post_to_slack("nq-intel", result.get("response", ""))


async def _daily_ops_check() -> None:
    """NQ-ANALYST-OPS: Check scoring pipeline, data quality."""
    from nq_api.slack.dispatcher import get_agent_for_channel

    agent = get_agent_for_channel("nq-analyst-ops")
    if agent:
        result = await agent.run(
            "Run daily ops check: scoring pipeline status, data freshness, score distribution.",
            {"channel": "nq-analyst-ops", "scheduled": True},
        )
        await _post_to_slack("nq-analyst-ops", result.get("response", ""))


async def _nightly_score_verify() -> None:
    """NQ-ANALYST-OPS: Verify nightly scoring completed."""
    from nq_api.slack.dispatcher import get_agent_for_channel

    agent = get_agent_for_channel("nq-analyst-ops")
    if agent:
        result = await agent.run(
            "Verify nightly scoring completed. Check score_cache row count, "
            "latest timestamp, score distribution. Report any anomalies.",
            {"channel": "nq-analyst-ops", "scheduled": True},
        )
        await _post_to_slack("nq-analyst-ops", result.get("response", ""))
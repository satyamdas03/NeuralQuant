"""Channel-to-agent routing and message dispatching."""

from __future__ import annotations

import json
import logging
from typing import Optional

from nq_api.slack.base import BaseSlackAgent

logger = logging.getLogger(__name__)

# Lazy-loaded agent instances
_AGENTS: dict[str, BaseSlackAgent] | None = None


def _init_agents() -> dict[str, BaseSlackAgent]:
    """Lazy-init all agents (called once)."""
    global _AGENTS
    if _AGENTS is not None:
        return _AGENTS

    from nq_api.slack.agents.engineer import EngineerAgent
    from nq_api.slack.agents.guardian import GuardianAgent
    from nq_api.slack.agents.content import ContentAgent
    from nq_api.slack.agents.analyst_ops import AnalystOpsAgent
    from nq_api.slack.agents.quant import QuantAgent
    from nq_api.slack.agents.biz import BizAgent
    from nq_api.slack.agents.intel import IntelAgent
    from nq_api.slack.agents.support import SupportAgent

    agents = [
        EngineerAgent(),
        GuardianAgent(),
        ContentAgent(),
        AnalystOpsAgent(),
        QuantAgent(),
        BizAgent(),
        IntelAgent(),
        SupportAgent(),
    ]
    _AGENTS = {agent.channel_name: agent for agent in agents}
    return _AGENTS


def get_agent_for_channel(channel_name: str) -> Optional[BaseSlackAgent]:
    """Map a Slack channel name to the correct agent."""
    agents = _init_agents()
    # Direct match: "nq-engineer" -> EngineerAgent
    if channel_name in agents:
        return agents[channel_name]
    # Fuzzy match: handle variations like "nq_engineer", "nqengineer"
    normalized = channel_name.replace("_", "-").replace(" ", "-").lower()
    return agents.get(normalized)


async def dispatch_message(
    channel_name: str, user_id: str, text: str, context: dict
) -> Optional[dict]:
    """Route a Slack message to the appropriate agent and return its response."""
    agent = get_agent_for_channel(channel_name)
    if not agent:
        logger.warning("No agent for channel: %s", channel_name)
        return None

    context["user_id"] = user_id
    context["channel"] = channel_name

    result = await agent.run(text, context)

    if result.get("needs_approval"):
        result["response"] = (
            f":warning: *Approval Required*\n\n"
            f"{result['response']}\n\n"
            f"_Reply with `approve` or `reject` to proceed._"
        )

    return result


async def log_agent_action(
    agent_name: str,
    channel: str,
    action_type: str,
    input_text: str,
    output_text: str,
    metadata: dict,
) -> None:
    """Log agent action to Supabase via httpx REST.

    Uses the same pattern as cache/score_cache.py to avoid
    RemoteProtocolError with the supabase-py SDK in async contexts.
    """
    import httpx
    import os

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url or not key:
        logger.warning("Supabase credentials not set, skipping agent log")
        return

    body = {
        "agent_name": agent_name,
        "channel": channel,
        "action_type": action_type,
        "input_text": input_text,
        "output_text": output_text,
        "metadata": json.dumps(metadata) if isinstance(metadata, dict) else metadata,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{url}/rest/v1/agent_logs",
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json=[body],
            )
            resp.raise_for_status()
    except Exception as exc:
        logger.error("Failed to log agent action to Supabase: %s", exc)
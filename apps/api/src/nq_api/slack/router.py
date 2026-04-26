"""FastAPI router for Slack agent system health endpoint."""

from fastapi import APIRouter

router = APIRouter(prefix="/slack", tags=["slack"])


@router.get("/health")
async def slack_health():
    """Health check for the Slack agent system.

    Returns whether the Slack Socket Mode handler is connected
    and which agents are available.
    """
    from nq_api.slack.app import _slack_app, _socket_handler
    from nq_api.slack.config import SLACK_BOT_TOKEN, SLACK_APP_TOKEN

    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        return {
            "status": "disabled",
            "reason": "SLACK_BOT_TOKEN or SLACK_APP_TOKEN not set",
            "agents": [],
        }

    from nq_api.slack.dispatcher import _init_agents

    agents = _init_agents()
    agent_list = [
        {
            "name": agent.agent_name,
            "channel": agent.channel_name,
            "model": agent._model,
        }
        for agent in agents.values()
    ]

    return {
        "status": "connected" if _socket_handler else "starting",
        "agents": agent_list,
    }
"""Base class for NeuralQuant Slack agents.

Each agent:
- Has a unique agent_name and channel mapping
- Receives Slack message events (not ticker+context)
- Builds its own system prompt dynamically
- Decides whether to respond directly or require human approval
- Logs all actions to Supabase agent_logs
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from abc import ABC, abstractmethod

import anthropic

from nq_api.slack.config import (
    AGENT_CONFIGS,
    FINANCIAL_APPROVAL_ACTIONS,
    ApprovalLevel,
)

logger = logging.getLogger(__name__)


class BaseSlackAgent(ABC):
    """Base class for all Slack-operated NeuralQuant agents."""

    agent_name: str
    channel_name: str
    approval_level: ApprovalLevel = ApprovalLevel.AUTO

    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY not set")
        self._client = anthropic.Anthropic(api_key=api_key, timeout=60.0)
        config = AGENT_CONFIGS.get(self.agent_name, {})
        self._model = config.get("model", "claude-haiku-4-5-20251001")

    @abstractmethod
    def build_system_prompt(self, context: dict) -> str:
        """Build the system prompt with any dynamic context injected."""
        ...

    @abstractmethod
    def build_user_message(self, text: str, context: dict) -> str:
        """Build the user message from the Slack event text + context."""
        ...

    def needs_approval(self, action_type: str) -> bool:
        """Whether this action requires human-in-the-loop approval.

        Financial actions ALWAYS require approval regardless of agent config.
        Other actions depend on the agent's requires_approval_for list.
        """
        if action_type in FINANCIAL_APPROVAL_ACTIONS:
            return True
        config = AGENT_CONFIGS.get(self.agent_name, {})
        approval_actions = config.get("requires_approval_for", [])
        return action_type in approval_actions

    def _detect_action_type(self, response: str) -> str:
        """Heuristic: detect action type from response text.

        Agents should include an ACTION tag: [ACTION:analysis] / [ACTION:deploy] etc.
        """
        match = re.search(r"\[ACTION:(\w+)\]", response)
        if match:
            return match.group(1).lower()
        return "analysis"

    async def run(self, text: str, context: dict) -> dict:
        """Run the agent and return a response dict.

        Returns: {
            "response": str,
            "action_type": str,
            "needs_approval": bool,
            "metadata": dict,
        }
        """
        system = self.build_system_prompt(context)
        user_msg = self.build_user_message(text, context)

        try:
            response = await asyncio.to_thread(
                self._client.messages.create,
                model=self._model,
                max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = ""
            for block in response.content:
                if hasattr(block, "text") and block.type == "text":
                    raw = block.text
                    break
            if not raw:
                raw = response.content[0].text if hasattr(response.content[0], "text") else ""

            action_type = self._detect_action_type(raw)
            needs_approval = self.needs_approval(action_type)

            usage = getattr(response, "usage", None)
            metadata = {
                "model": self._model,
                "tokens": {
                    "input": usage.input_tokens if usage else 0,
                    "output": usage.output_tokens if usage else 0,
                },
            }

            result = {
                "response": raw,
                "action_type": action_type,
                "needs_approval": needs_approval,
                "metadata": metadata,
            }

            # Log to Supabase
            await self._log_action(text, result, context)

            return result

        except Exception as exc:
            logger.error("%s agent failed: %s", self.agent_name, exc, exc_info=True)
            return {
                "response": (
                    f"Error: {self.agent_name} encountered an issue. "
                    f"Details: {str(exc)[:200]}"
                ),
                "action_type": "error",
                "needs_approval": False,
                "metadata": {"error": str(exc)},
            }

    async def _log_action(self, input_text: str, result: dict, context: dict) -> None:
        """Log this action to Supabase agent_logs."""
        try:
            from nq_api.slack.dispatcher import log_agent_action

            await log_agent_action(
                agent_name=self.agent_name,
                channel=context.get("channel", self.channel_name),
                action_type=result.get("action_type", "unknown"),
                input_text=input_text[:2000],
                output_text=result.get("response", "")[:4000],
                metadata=result.get("metadata", {}),
            )
        except Exception as exc:
            logger.warning("Failed to log agent action: %s", exc)
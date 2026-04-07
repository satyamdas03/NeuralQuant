"""Base agent class for NeuralQuant PARA-DEBATE analyst team."""
from __future__ import annotations
import logging
import os
import re
from abc import ABC, abstractmethod

import anthropic

from nq_api.schemas import AgentOutput

logger = logging.getLogger(__name__)
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1024


class BaseAnalystAgent(ABC):
    """One analyst in the PARA-DEBATE panel."""

    agent_name: str
    system_prompt: str

    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Set it before instantiating any agent."
            )
        self._client = anthropic.Anthropic(api_key=api_key)

    @abstractmethod
    def _build_user_message(self, ticker: str, context: dict) -> str:
        ...

    def run(self, ticker: str, context: dict) -> AgentOutput:
        user_msg = self._build_user_message(ticker, context)
        try:
            response = self._client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=self.system_prompt,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = response.content[0].text
            return self._parse_output(raw)
        except Exception as exc:
            logger.warning(
                "%s agent failed for %s: %s — returning neutral fallback",
                self.agent_name, ticker, exc,
            )
            return self._neutral_fallback()

    def _parse_output(self, raw: str) -> AgentOutput:
        try:
            stance = re.search(r"STANCE:\s*(BULL|BEAR|NEUTRAL)", raw, re.I).group(1).upper()
            conviction = re.search(r"CONVICTION:\s*(HIGH|MEDIUM|LOW)", raw, re.I).group(1).upper()
            thesis_match = re.search(r"THESIS:\s*(.+?)(?=KEY_POINTS:|\Z)", raw, re.I | re.S)
            thesis = thesis_match.group(1).strip() if thesis_match else raw[:200]
            points_raw = re.search(r"KEY_POINTS:(.*)", raw, re.I | re.S)
            if points_raw:
                points = [
                    re.sub(r"^[-*•]\s*|^\d+\.\s*", "", p.strip()).strip()
                    for p in points_raw.group(1).strip().splitlines()
                    if p.strip() and p.strip() not in ("-", "*", "•")
                ]
            else:
                points = [thesis[:100]]

            return AgentOutput(
                agent=self.agent_name,
                stance=stance,
                conviction=conviction,
                thesis=thesis[:500],
                key_points=points[:5],
            )
        except Exception:
            return self._neutral_fallback()

    def _neutral_fallback(self) -> AgentOutput:
        name = getattr(self, "agent_name", "UNKNOWN")
        return AgentOutput(
            agent=name,
            stance="NEUTRAL",
            conviction="LOW",
            thesis=f"{name} analysis unavailable.",
            key_points=["Insufficient data for analysis."],
        )

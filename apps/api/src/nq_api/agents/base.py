"""Base agent class for NeuralQuant PARA-DEBATE analyst team."""
from __future__ import annotations
import os
import re
from abc import ABC, abstractmethod

import anthropic

from nq_api.schemas import AgentOutput

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024


class BaseAnalystAgent(ABC):
    """One analyst in the PARA-DEBATE panel."""

    agent_name: str
    system_prompt: str

    def __init__(self):
        self._client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

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
        except Exception:
            return self._neutral_fallback()

    def _parse_output(self, raw: str) -> AgentOutput:
        try:
            stance = re.search(r"STANCE:\s*(BULL|BEAR|NEUTRAL)", raw, re.I).group(1).upper()
            conviction = re.search(r"CONVICTION:\s*(HIGH|MEDIUM|LOW)", raw, re.I).group(1).upper()
            thesis_match = re.search(r"THESIS:\s*(.+?)(?=KEY_POINTS:|$)", raw, re.I | re.S)
            thesis = thesis_match.group(1).strip() if thesis_match else raw[:200]
            points_raw = re.search(r"KEY_POINTS:(.*)", raw, re.I | re.S)
            if points_raw:
                points = [
                    p.strip().lstrip("-").strip()
                    for p in points_raw.group(1).strip().splitlines()
                    if p.strip().lstrip("-").strip()
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
        return AgentOutput(
            agent=self.agent_name,
            stance="NEUTRAL",
            conviction="LOW",
            thesis=f"{self.agent_name} analysis unavailable.",
            key_points=["Insufficient data for analysis."],
        )

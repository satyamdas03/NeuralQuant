"""Base agent class for NeuralQuant PARA-DEBATE analyst team."""
from __future__ import annotations
import logging
import os
import re
from abc import ABC, abstractmethod

import anthropic

from nq_api.schemas import AgentOutput

logger = logging.getLogger(__name__)
MODEL = os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4-6")
# Fast model for 5 specialist + adversarial agents (2-5s vs 10-30s Sonnet)
FAST_MODEL = os.environ.get("NQ_FAST_MODEL", "claude-haiku-4-5-20251001")
MAX_TOKENS = 4096


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
        self._client = anthropic.Anthropic(api_key=api_key, timeout=45.0)

    @abstractmethod
    def _build_user_message(self, ticker: str, context: dict) -> str:
        ...

    def run(self, ticker: str, context: dict) -> AgentOutput:
        user_msg = self._build_user_message(ticker, context)
        try:
            response = self._client.messages.create(
                model=FAST_MODEL,
                max_tokens=MAX_TOKENS,
                system=self.system_prompt,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = ""
            for block in response.content:
                if block.type == "text":
                    raw = block.text
                    break
            if not raw:
                raw = response.content[0].text if hasattr(response.content[0], "text") else ""
            parsed = self._parse_output(raw)
            if parsed.thesis and "insufficient" not in parsed.thesis.lower():
                return parsed
            # Retry once with simplified prompt
            return self._retry_with_simplified(ticker, context) or self._neutral_fallback(ticker, context)
        except Exception as exc:
            logger.warning(
                "%s agent failed for %s: %s — retrying with simplified prompt",
                self.agent_name, ticker, exc,
            )
            retry_result = self._retry_with_simplified(ticker, context)
            return retry_result or self._neutral_fallback(ticker, context)

    def _retry_with_simplified(self, ticker: str, context: dict) -> AgentOutput | None:
        """Retry with a shorter prompt using only essential context fields."""
        essential_keys = [
            "price", "change_pct", "pe_ttm", "pb_ratio", "market_cap",
            "composite_score", "regime_label", "sector", "momentum_percentile",
            "quality_percentile", "value_percentile", "low_vol_percentile",
        ]
        simplified_ctx = {k: v for k, v in context.items() if k in essential_keys and v is not None}
        if not simplified_ctx:
            return None
        user_msg = self._build_user_message(ticker, simplified_ctx)
        try:
            response = self._client.messages.create(
                model=FAST_MODEL,
                max_tokens=2048,
                system=self.system_prompt + "\n\nSimplified context — use only the data provided. Be concise.",
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = ""
            for block in response.content:
                if block.type == "text":
                    raw = block.text
                    break
            if raw:
                parsed = self._parse_output(raw)
                if parsed.thesis and "insufficient" not in parsed.thesis.lower():
                    return parsed
        except Exception:
            pass
        return None

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

    def _neutral_fallback(self, ticker: str = "", context: dict | None = None) -> AgentOutput:
        name = getattr(self, "agent_name", "UNKNOWN")
        available = [k for k in (context or {}) if context.get(k) is not None and k != "ticker"][:10]
        thesis = (
            f"{name} could not reach a conclusion on {ticker}. "
            f"Data available: {', '.join(available)}. "
            f"Limited data prevented definitive analysis."
            if available
            else f"{name} analysis unavailable — no data received."
        )
        return AgentOutput(
            agent=name,
            stance="NEUTRAL",
            conviction="LOW",
            thesis=thesis,
            key_points=["Insufficient signal strength for directional call."],
        )

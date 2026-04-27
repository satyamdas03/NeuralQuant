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
FAST_MODEL = os.environ.get("NQ_FAST_MODEL", os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL", "claude-3-5-haiku-20241022"))
MAX_TOKENS = 4096

def _is_ollama() -> bool:
    """Runtime Ollama detection — avoids module-level env var issues in uvicorn."""
    url = os.environ.get("ANTHROPIC_BASE_URL", "")
    return "127.0.0.1:11434" in url or "localhost:11434" in url


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
        client_timeout = 90.0 if _is_ollama() else 45.0
        self._client = anthropic.Anthropic(api_key=api_key, timeout=client_timeout)

    @abstractmethod
    def _build_user_message(self, ticker: str, context: dict) -> str:
        ...

    def run(self, ticker: str, context: dict) -> AgentOutput:
        user_msg = self._build_user_message(ticker, context)
        ctx_keys = [k for k in context if context.get(k) is not None and k != "ticker"][:5]
        logger.info("%s agent starting for %s (context keys: %s...)", self.agent_name, ticker, ctx_keys)
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
            parsed = self._parse_output(raw, ticker, context)
            if parsed.thesis and "insufficient" not in parsed.thesis.lower():
                return parsed
            # Retry once with simplified prompt
            return self._retry_with_simplified(ticker, context) or self._neutral_fallback(ticker, context)
        except Exception as exc:
            logger.warning(
                "%s agent failed for %s: %s (%s) — retrying with simplified prompt",
                self.agent_name, ticker, type(exc).__name__, exc,
            )
            retry_result = self._retry_with_simplified(ticker, context)
            return retry_result or self._neutral_fallback(ticker, context)

    def run_with_retry(self, ticker: str, context: dict, max_attempts: int = 3) -> AgentOutput:
        """Run agent with retry delays for Ollama (single-threaded model server)."""
        for attempt in range(max_attempts):
            result = self.run(ticker, context)
            if result.stance != "NEUTRAL" or result.conviction != "LOW":
                return result
            if attempt < max_attempts - 1:
                import time
                time.sleep(2)  # Brief pause between retries for Ollama
        return self.run(ticker, context)

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
                parsed = self._parse_output(raw, ticker, context)
                if parsed.thesis and "insufficient" not in parsed.thesis.lower():
                    return parsed
        except Exception:
            pass
        return None

    def _parse_output(self, raw: str, ticker: str = "", context: dict | None = None) -> AgentOutput:
        try:
            # Lenient stance extraction — handles "STANCE: BULL", "Stance: Bull", "bull", "**BULL**", etc.
            stance_match = re.search(r"(?:STANCE|Stance|stance)[:\s]*\*{0,2}(BULL|BEAR|NEUTRAL)\*{0,2}", raw, re.I)
            if not stance_match:
                # Fallback: look for bare stance word at start of line or after newline
                stance_match = re.search(r"^[\s*-]*(BULL|BEAR|NEUTRAL)\b", raw, re.I | re.M)
            if not stance_match:
                # Last resort: find first occurrence anywhere
                stance_match = re.search(r"\b(BULL|BEAR|NEUTRAL)\b", raw, re.I)
            stance = stance_match.group(1).upper() if stance_match else "NEUTRAL"

            conviction_match = re.search(r"(?:CONVICTION|Conviction|conviction)[:\s]*\*{0,2}(HIGH|MEDIUM|LOW)\*{0,2}", raw, re.I)
            if not conviction_match:
                conviction_match = re.search(r"\b(HIGH|MEDIUM|LOW)\s+conviction\b", raw, re.I)
            conviction = conviction_match.group(1).upper() if conviction_match else "MEDIUM"

            thesis_match = re.search(r"THESIS:\s*(.+?)(?=KEY_POINTS:|RISK_FACTORS:|VERDICT:|\Z)", raw, re.I | re.S)
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
            return self._neutral_fallback(ticker, context)

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

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
# Fast model for 5 specialist + adversarial agents.
# Default: Sonnet (works on all API tiers; Haiku 3.5 model name deprecated on some plans).
# Set NQ_FAST_MODEL to a Haiku model ID if your API key supports it for faster/cheaper calls.
FAST_MODEL = os.environ.get("NQ_FAST_MODEL", MODEL)
MAX_TOKENS = 4096

# Validate model availability at first use — falls back to MODEL if fast model is unavailable
_validated_models: dict[str, bool] = {}

def _is_ollama() -> bool:
    """Runtime Ollama detection — avoids module-level env var issues in uvicorn."""
    url = os.environ.get("ANTHROPIC_BASE_URL", "")
    return "127.0.0.1:11434" in url or "localhost:11434" in url


def _resolve_model(preferred: str, fallback: str) -> str:
    """Return preferred if validated, else fallback. Validates once, caches result."""
    if preferred in _validated_models:
        return preferred if _validated_models[preferred] else fallback
    # One-shot validation: try a minimal completion with the preferred model
    try:
        client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            timeout=10.0,
        )
        resp = client.messages.create(
            model=preferred, max_tokens=5,
            messages=[{"role": "user", "content": "hi"}],
        )
        _validated_models[preferred] = bool(resp and resp.content)
        if _validated_models[preferred]:
            logger.info("Model %s validated — using as fast model", preferred)
            return preferred
    except Exception as exc:
        logger.warning("Model %s unavailable (%s: %s) — falling back to %s", preferred, type(exc).__name__, exc, fallback)
        _validated_models[preferred] = False
    return fallback


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
        # Resolve fast model — fall back to MODEL if preferred model is unavailable
        self._model = _resolve_model(FAST_MODEL, MODEL)

    @abstractmethod
    def _build_user_message(self, ticker: str, context: dict) -> str:
        ...

    def run(self, ticker: str, context: dict) -> AgentOutput:
        user_msg = self._build_user_message(ticker, context)
        ctx_keys = [k for k in context if context.get(k) is not None and k != "ticker"][:5]
        logger.info("%s agent starting for %s (context keys: %s...)", self.agent_name, ticker, ctx_keys)
        try:
            response = self._client.messages.create(
                model=self._model,
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
                model=self._model,
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
        # Show stock-specific keys first (more useful for debugging than macro keys)
        stock_keys = ["composite_score", "pe_ttm", "pb_ratio", "beta", "market_cap",
                      "gross_profit_margin", "piotroski", "momentum_raw", "short_interest_pct"]
        macro_keys = ["vix", "regime_label", "spx_return_1m", "yield_10y"]
        available_stock = [k for k in stock_keys if context and context.get(k) is not None]
        available_macro = [k for k in macro_keys if context and context.get(k) is not None]
        if available_stock or available_macro:
            stock_str = f"stock: {', '.join(available_stock)}" if available_stock else "no stock data"
            macro_str = f"macro: {', '.join(available_macro)}" if available_macro else ""
            data_desc = f"{stock_str}; {macro_str}".strip("; ")
            thesis = f"{name} could not reach a conclusion on {ticker}. Data present: {data_desc}. The LLM call likely failed — check model availability and API access."
        else:
            thesis = f"{name} analysis unavailable — no data received for {ticker}."
        return AgentOutput(
            agent=name,
            stance="NEUTRAL",
            conviction="LOW",
            thesis=thesis,
            key_points=["Agent LLM call failed or returned unparseable output."],
        )

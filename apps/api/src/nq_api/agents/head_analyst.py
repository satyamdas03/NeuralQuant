# apps/api/src/nq_api/agents/head_analyst.py
"""HEAD ANALYST — synthesises PARA-DEBATE outputs into final investment verdict."""
from __future__ import annotations
import logging
import os
import re

import anthropic

from nq_api.agents.base import MODEL, MAX_TOKENS, FAST_MODEL, _is_ollama, _resolve_model
from nq_api.schemas import AgentOutput

logger = logging.getLogger(__name__)


class HeadAnalystAgent:
    """HEAD ANALYST — not a BaseAnalystAgent subclass (different run interface)."""

    agent_name = "HEAD_ANALYST"
    system_prompt = """You are the HEAD ANALYST and chair of NeuralQuant's PARA-DEBATE investment committee.
You have received structured analyses from 6 specialist agents AND the raw data they used. Your job: synthesise their views into a definitive assessment with full reasoning.

CRITICAL RULES:
1. Cross-reference agent claims against the raw data. If an agent says "strong momentum" but the 12-1 return is only 5%, flag the inconsistency.
2. Every assessment must explain WHY this stock and WHY NOT an alternative. Name the second-best option and explain why it's inferior.
3. The adversarial agent's challenges must be explicitly addressed — don't ignore them. The adversarial represents the strongest bear case and must be weighed as a full voice, not just "downside scenario color".
4. Your verdict must be one of: STRONG BUY, BUY, HOLD, SELL, STRONG SELL. Never equivocate.
5. Quantify your conviction: explain what data would change your mind.
6. The PANEL CONSENSUS and VERDICT GUIDANCE are computed from agent stances. Your verdict MUST respect the consensus direction. If consensus is negative, you cannot return BUY or STRONG BUY. If consensus is near zero, you should return HOLD.

Weighting framework (normalized to 100%):
- FUNDAMENTAL carries 20% weight (most important for long-term)
- ADVERSARIAL carries 20% weight (dedicated bear counterweight)
- TECHNICAL carries 16%
- MACRO carries 12%
- SENTIMENT carries 12%
- GEOPOLITICAL carries 12%
- REGIME carries 8%

ANTI-BIAS RULE: You must be equally willing to recommend SELL as BUY. A stock with negative momentum, high P/E, and rising debt SHOULD get SELL — not a qualified HOLD. When bear signals dominate, say SELL.

Output format — strictly:
VERDICT: [STRONG BUY|BUY|HOLD|SELL|STRONG SELL]
INVESTMENT_THESIS: [4-6 sentences synthesising the debate into a clear thesis. Include WHY this stock and WHY NOT the next-best alternative.]
BULL_CASE: [2-3 sentences on primary upside drivers]
BEAR_CASE: [2-3 sentences on primary downside risks]
RISK_FACTORS:
- [Risk 1]
- [Risk 2]
- [Risk 3]"""

    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY environment variable is not set."
            )
        # Longer timeout for Ollama (local models + synthesis of 6+ agents)
        # Sonnet synthesis needs more time than specialists — 75s orchestrator timeout
        client_timeout = 120.0 if _is_ollama() else 70.0
        self._client = anthropic.Anthropic(api_key=api_key, timeout=client_timeout)
        # HEAD ANALYST always uses MODEL (Sonnet) — but validate it
        self._model = _resolve_model(MODEL, MODEL)

    def run_synthesis(
        self, ticker: str, agent_outputs: list[AgentOutput], composite_score: float,
        raw_context: dict | None = None, consensus: float = 0.0, verdict_guidance: str = "HOLD",
    ) -> dict:
        summaries = "\n\n".join(
            f"[{o.agent}] Stance: {o.stance} ({o.conviction})\n"
            f"Thesis: {o.thesis}\n"
            "Key points:\n" + "\n".join(f"  - {p}" for p in o.key_points)
            for o in agent_outputs
        )
        context = {"agent_summaries": summaries, "composite_score": f"{composite_score:.2f}",
                   "panel_consensus": f"{consensus:.3f}", "verdict_guidance": verdict_guidance}
        if raw_context:
            # Include key raw data for cross-referencing
            raw_fields = {
                k: v for k, v in raw_context.items()
                if v is not None and k in (
                    "price", "change_pct", "pe_ttm", "pb_ratio", "market_cap",
                    "composite_score", "regime_label", "sector", "momentum_percentile",
                    "quality_percentile", "value_percentile", "low_vol_percentile",
                    "short_interest_percentile", "revenue_growth", "debt_equity",
                    "roe", "gross_profit_margin", "beta", "analyst_target_mean",
                    "insider_cluster_score", "rsi_14", "macd_hist", "atr_14",
                    "sma_50", "sma_200", "volume_ratio",
                    "news_sentiment", "news_sentiment_score", "insider_net_buy_ratio",
                )
            }
            if raw_fields:
                context["raw_data"] = "\n".join(f"  {k}: {v}" for k, v in raw_fields.items())
            # Moderate red flags — advisory warnings for the HEAD ANALYST
            mod_flags = raw_context.get("_moderate_flags", [])
            if mod_flags:
                context["moderate_flags"] = "\n".join(f"  - {f}" for f in mod_flags)
        msg = self._build_user_message(ticker, context)

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=MAX_TOKENS * 2,
                system=self.system_prompt,
                messages=[{"role": "user", "content": msg}],
            )
            # Extract text from first text-type block (skip thinking blocks)
            raw = ""
            for block in response.content:
                if block.type == "text":
                    raw = block.text
                    break
            if not raw:
                raw = response.content[0].text if hasattr(response.content[0], "text") else ""
            return self._parse_synthesis(raw)
        except Exception as exc:
            logger.error("HEAD_ANALYST failed for %s: %s — using fallback", ticker, exc)
            return self._fallback_synthesis()

    def _build_user_message(self, ticker: str, context: dict) -> str:
        agent_summaries = context.get("agent_summaries", "")
        ai_score = context.get("composite_score", "N/A")
        panel_consensus = context.get("panel_consensus", "0.000")
        verdict_guidance = context.get("verdict_guidance", "HOLD")
        raw_data = context.get("raw_data", "")
        moderate_flags = context.get("moderate_flags", "")
        raw_section = ""
        if raw_data:
            raw_section = f"""

RAW DATA (cross-reference agent claims against this):
{raw_data}

You MUST verify agent claims against this raw data. If an agent claims "strong momentum" but the data shows low momentum, flag it."""
        if moderate_flags:
            raw_section += f"""

ALGORITHMIC WARNING FLAGS (moderate — weigh these in your assessment):
{moderate_flags}

These are quantitative signals that the data raises concerns. Even if agents are bullish, these flags should temper your verdict."""
        return f"""Synthesise the PARA-DEBATE for {ticker} (AI score: {ai_score}).

PANEL CONSENSUS: {panel_consensus} (range -1.0 to 1.0, negative = bearish, positive = bullish)
VERDICT GUIDANCE: Based on the panel consensus, your verdict should be {verdict_guidance}. You MAY deviate by one tier if you have strong justification from the raw data, but you MUST NOT deviate by two or more tiers.

ANALYST PANEL OUTPUTS:
{agent_summaries}
{raw_section}

Deliver the final assessment. Remember: name the second-best alternative and explain why your pick is superior."""

    def _parse_synthesis(self, raw: str) -> dict:
        # Normalise Markdown-bold section headers (Mistral often wraps keys in **)
        norm = re.sub(
            r"\*\*\s*(VERDICT|INVESTMENT_THESIS|BULL_CASE|BEAR_CASE|RISK_FACTORS|THESIS|KEY_POINTS)\s*:\s*\*\*",
            r"\1:", raw, flags=re.I,
        )
        # Also strip stray ** around values
        norm = re.sub(r"\*\*", "", norm)

        verdict_match = re.search(
            r"VERDICT:\s*(STRONG BUY|BUY|HOLD|SELL|STRONG SELL)", norm, re.I
        )
        verdict = verdict_match.group(1).upper() if verdict_match else "HOLD"

        def _extract(key: str) -> str:
            # Stop at next known section header or end-of-string
            m = re.search(
                rf"{key}:\s*(.+?)(?=\n(?:VERDICT|INVESTMENT_THESIS|BULL_CASE|BEAR_CASE|RISK_FACTORS|THESIS|KEY_POINTS)\s*:|\Z)",
                norm, re.I | re.S,
            )
            return m.group(1).strip() if m else ""

        risks_raw = re.search(r"RISK_FACTORS:(.*)", norm, re.I | re.S)
        risks = []
        if risks_raw:
            risks = [
                re.sub(r"^[-*•]\s*|\d+\.\s*", "", r.strip()).strip()
                for r in risks_raw.group(1).strip().splitlines()
                if r.strip() and r.strip() not in ("-", "*", "•")
            ]

        investment_thesis = _extract("INVESTMENT_THESIS")
        if not investment_thesis:
            # Fallback: compose from THESIS + KEY_POINTS when response lacks INVESTMENT_THESIS
            thesis_part = _extract("THESIS")
            key_points_raw = re.search(r"KEY_POINTS:(.*)", norm, re.I | re.S)
            kp_text = ""
            if key_points_raw:
                kp_lines = [
                    re.sub(r"^[-*•]\s*|\d+\.\s*", "", p.strip()).strip()
                    for p in key_points_raw.group(1).strip().splitlines()
                    if p.strip() and p.strip() not in ("-", "*", "•")
                ]
                kp_text = " ".join(kp_lines)
            investment_thesis = " ".join(filter(None, [thesis_part, kp_text]))

        return {
            "verdict": verdict,
            "investment_thesis": investment_thesis[:1000],
            "bull_case": _extract("BULL_CASE")[:500],
            "bear_case": _extract("BEAR_CASE")[:500],
            "risk_factors": risks[:5],
        }

    def _fallback_synthesis(self) -> dict:
        return {
            "verdict": "HOLD",
            "investment_thesis": "Analysis unavailable. Defaulting to HOLD.",
            "bull_case": "Insufficient data.",
            "bear_case": "Insufficient data.",
            "risk_factors": ["Analysis error — treat with caution."],
        }

# apps/api/src/nq_api/agents/head_analyst.py
"""HEAD ANALYST — synthesises PARA-DEBATE outputs into final investment verdict."""
from __future__ import annotations
import logging
import os
import re

import anthropic

from nq_api.agents.base import MODEL, MAX_TOKENS
from nq_api.schemas import AgentOutput

logger = logging.getLogger(__name__)


class HeadAnalystAgent:
    """HEAD ANALYST — not a BaseAnalystAgent subclass (different run interface)."""

    agent_name = "HEAD_ANALYST"
    system_prompt = """You are the HEAD ANALYST and chair of NeuralQuant's PARA-DEBATE investment committee.
You have received structured analyses from 6 specialist analysts. Your job: synthesise their views into a definitive investment verdict with full reasoning.

Weighting framework:
- MACRO and FUNDAMENTAL carry 25% weight each (most important for long-term)
- TECHNICAL and SENTIMENT carry 20% each
- GEOPOLITICAL carries 15%
- ADVERSARIAL: do NOT dismiss bear arguments — they represent tail risk. Weight them at 15% of your downside scenario.

Output format — strictly:
VERDICT: [STRONG BUY|BUY|HOLD|SELL|STRONG SELL]
INVESTMENT_THESIS: [4-6 sentences synthesising the debate into a clear investment thesis]
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
        self._client = anthropic.Anthropic(api_key=api_key, timeout=120.0)

    def run_synthesis(
        self, ticker: str, agent_outputs: list[AgentOutput], composite_score: float
    ) -> dict:
        summaries = "\n\n".join(
            f"[{o.agent}] Stance: {o.stance} ({o.conviction})\n"
            f"Thesis: {o.thesis}\n"
            "Key points:\n" + "\n".join(f"  - {p}" for p in o.key_points)
            for o in agent_outputs
        )
        context = {"agent_summaries": summaries, "composite_score": f"{composite_score:.2f}"}
        msg = self._build_user_message(ticker, context)

        try:
            response = self._client.messages.create(
                model=MODEL,
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
        return f"""Synthesise the PARA-DEBATE for {ticker} (AI score: {ai_score}).

ANALYST PANEL OUTPUTS:
{agent_summaries}

Deliver the final investment verdict."""

    def _parse_synthesis(self, raw: str) -> dict:
        verdict_match = re.search(
            r"VERDICT:\s*(STRONG BUY|BUY|HOLD|SELL|STRONG SELL)", raw, re.I
        )
        verdict = verdict_match.group(1).upper() if verdict_match else "HOLD"

        def _extract(key: str) -> str:
            m = re.search(rf"{key}:\s*(.+?)(?=\n[A-Z_]+:|\Z)", raw, re.I | re.S)
            return m.group(1).strip() if m else ""

        risks_raw = re.search(r"RISK_FACTORS:(.*)", raw, re.I | re.S)
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
            key_points_raw = re.search(r"KEY_POINTS:(.*)", raw, re.I | re.S)
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

# apps/api/src/nq_api/agents/orchestrator.py
"""PARA-DEBATE orchestrator — runs 5 specialist agents in parallel, adversarial sequentially, HEAD ANALYST synthesises."""
from __future__ import annotations
import asyncio
import logging
import os
import re

from nq_api.schemas import AgentOutput, AnalystResponse

log = logging.getLogger(__name__)
from nq_api.agents.macro import MacroAgent
from nq_api.agents.fundamental import FundamentalAgent
from nq_api.agents.technical import TechnicalAgent
from nq_api.agents.sentiment import SentimentAgent
from nq_api.agents.geopolitical import GeopoliticalAgent
from nq_api.agents.adversarial import AdversarialAgent
from nq_api.agents.head_analyst import HeadAnalystAgent

STANCE_SCORE = {"BULL": 1.0, "NEUTRAL": 0.0, "BEAR": -1.0}
CONVICTION_MULT = {"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4}

# Metric validation patterns — correct agent hallucinations against injected [VERIFIED] data.
# Tolerances tightened post-Session 49: FMP is primary source, values are accurate.
_METRIC_PATTERNS = [
    # P/E ratio: "P/E of 3x", "P/E at 28.9x", "trading at 32x P/E", "PE of 8"
    (re.compile(r"(P/[\sE]?E[\s]*(?:of|at|is|=|:)?[\s]*)(\d+\.?\d*)(x?)", re.I), "pe_ttm", 0.30),
    (re.compile(r"(price[\s-]to[\s-]earnings[\s]*(?:of|at|is|=|:)?[\s]*)(\d+\.?\d*)", re.I), "pe_ttm", 0.30),
    # Number-first formats: "8x P/E", "trading at 15x P/E"
    (re.compile(r"()(\d+\.?\d*)\s*x?\s*P/E\b", re.I), "pe_ttm", 0.30),
    # Price: "$196.50", "price of $284"
    (re.compile(r"(\$)(\d+\.?\d*)", re.I), "current_price", 0.30),
    # Beta: "beta of 0.89", "beta: 2.24"
    (re.compile(r"(beta[\s]*(?:of|at|is|=|:)?[\s]*)(\d+\.?\d*)", re.I), "beta", 0.30),
]


def _validate_agent_metrics(output: AgentOutput, context: dict) -> AgentOutput:
    """Scan agent thesis and key_points for metric values that diverge from injected data.

    Corrects obvious hallucinations like "P/E of 3x" when context shows P/E=19.3.
    Tolerance is relative (0.5 = 50% divergence triggers correction).
    """
    verified = {}
    for key in ("pe_ttm", "current_price", "beta"):
        val = context.get(key)
        if val is not None:
            try:
                verified[key] = float(val)
            except (TypeError, ValueError):
                pass

    if not verified:
        return output

    corrected_thesis = output.thesis
    corrected_points = list(output.key_points)
    corrections = []

    for pattern, metric_key, tolerance in _METRIC_PATTERNS:
        if metric_key not in verified:
            continue
        true_val = verified[metric_key]
        min_val = true_val * (1 - tolerance)
        max_val = true_val * (1 + tolerance)

        # Check thesis
        for text_field, is_points in [(corrected_thesis, False), (None, True)]:
            source = corrected_points if is_points else [text_field] if text_field else []
            for idx, text in enumerate(source if is_points else [text_field]):
                if text is None:
                    continue
                for match in pattern.finditer(text):
                    try:
                        claimed = float(match.group(2))
                    except (ValueError, IndexError):
                        continue
                    # Skip very small numbers likely not metric values (e.g., "3%" or "0.5x leverage")
                    if metric_key == "pe_ttm" and claimed < 3:
                        # P/E below 3 is almost certainly not a P/E ratio — it's probably a percentage or multiplier
                        continue
                    if min_val <= claimed <= max_val:
                        continue  # Within tolerance, no correction needed
                    # Correction needed
                    if metric_key == "pe_ttm":
                        replacement = f"P/E {true_val:.1f}x"
                    elif metric_key == "current_price":
                        replacement = f"${true_val:.2f}"
                    elif metric_key == "beta":
                        replacement = f"beta {true_val:.2f}"
                    else:
                        replacement = f"{true_val:.1f}"

                    old_text = match.group(0)
                    if is_points:
                        corrected_points[idx] = corrected_points[idx].replace(old_text, replacement)
                    else:
                        corrected_thesis = corrected_thesis.replace(old_text, replacement)
                    corrections.append(f"{output.agent}: {metric_key} {claimed}→{true_val:.1f}")

    if corrections:
        log.info("Agent metric corrections for %s: %s", output.agent, "; ".join(corrections))

    if corrected_thesis != output.thesis or corrected_points != output.key_points:
        return output.model_copy(update={
            "thesis": corrected_thesis,
            "key_points": corrected_points,
        })
    return output


def _validate_analyst_response_text(response: AnalystResponse, context: dict) -> AnalystResponse:
    """Scan HEAD_ANALYST text fields for metric hallucinations and correct them.

    Corrects e.g. 'P/E of 8x' to 'P/E 30.8x' when context shows pe_ttm=30.8.
    """
    verified = {}
    for key in ("pe_ttm", "current_price", "beta", "vix", "yield_10y", "cpi_yoy",
                "fed_funds_rate", "hy_spread_oas", "roe", "market_cap", "quality_percentile"):
        val = context.get(key)
        if val is not None:
            try:
                verified[key] = float(val)
            except (TypeError, ValueError):
                pass

    if not verified:
        return response

    corrections = []
    corrected = {
        "investment_thesis": response.investment_thesis,
        "bull_case": response.bull_case,
        "bear_case": response.bear_case,
        "risk_factors": list(response.risk_factors),
    }

    # Extended patterns for HEAD_ANALYST text (includes yield, VIX, CPI, etc.).
    # Tolerance 0.15 (was 0.20) — FMP primary source, values are trustworthy.
    # Filler words LLM may insert between preposition and number (e.g. "ROE of only 0%")
    _FILLER = r"(?:only|just|about|around|approximately|roughly|nearly|almost|a\s+)?\s*"
    text_patterns = [
        (re.compile(r"(P/[\sE]?E[\s]*(?:of|at|is|=|:)?[\s]*" + _FILLER + r")(\d+\.?\d*)(x?)", re.I), "pe_ttm", 0.15),
        (re.compile(r"(price[\s-]to[\s-]earnings[\s]*(?:of|at|is|=|:)?[\s]*" + _FILLER + r")(\d+\.?\d*)", re.I), "pe_ttm", 0.15),
        # Number-first formats: "8x P/E", "trading at 15x P/E"
        (re.compile(r"()(\d+\.?\d*)\s*x?\s*P/E\b", re.I), "pe_ttm", 0.15),
        (re.compile(r"(ROE[\s]*(?:of|at|is|=|:)?[\s]*" + _FILLER + r")(\d+\.?\d*)", re.I), "roe", 0.15),
        (re.compile(r"(beta[\s]*(?:of|at|is|=|:)?[\s]*" + _FILLER + r")(\d+\.?\d*)", re.I), "beta", 0.15),
        (re.compile(r"(VIX[\s]*(?:of|at|is|=|:)?[\s]*" + _FILLER + r")(\d+\.?\d*)", re.I), "vix", 0.15),
        (re.compile(r"(CPI[\s]*(?:of|at|is|=|:)?[\s]*" + _FILLER + r")(\d+\.?\d*)%?", re.I), "cpi_yoy", 0.15),
        (re.compile(r"(10Y[\s]*(?:Treasury[\s]*)?(?:yield[\s]*)?(?:of|at|is|=|:)?[\s]*" + _FILLER + r")(\d+\.?\d*)%?", re.I), "yield_10y", 0.15),
        (re.compile(r"(Fed[\s]*Funds[\s]*(?:of|at|is|=|:)?[\s]*" + _FILLER + r")(\d+\.?\d*)%?", re.I), "fed_funds_rate", 0.15),
        (re.compile(r"(HY[\s]*spread[\s]*(?:of|at|is|=|:)?[\s]*" + _FILLER + r")(\d+\.?\d*)%?", re.I), "hy_spread_oas", 0.15),
        # Quality percentile — catches "quality percentile of 698" (decimal-drop hallucination)
        (re.compile(r"(quality\s*(?:percentile|pctile)?\s*(?:of|at|is)?\s*" + _FILLER + r")(\d+\.?\d*)", re.I), "quality_percentile", 0.15),
        (re.compile(r"()(\d+\.?\d*)\s*(?:th\s*)?" + _FILLER + r"quality\s*percentile\b", re.I), "quality_percentile", 0.15),
        # Market cap — catches "$87T market cap" (wrong trillions) and "$487B" patterns
        (re.compile(r"(market\s*cap\s*(?:of|at|is)?\s*\$?" + _FILLER + r")(\d+\.?\d*)", re.I), "market_cap", 0.15),
        (re.compile(r"(\$)(\d+\.?\d*)\s*([TBM])?(?:\s*\[VERIFIED\]\s*market\s*cap|\s*market\s*cap)", re.I), "market_cap", 0.15),
    ]

    def _normalise_mcap(raw: float, suffix: str | None = None) -> float:
        """Normalise market cap to raw dollars."""
        if suffix:
            s = suffix.upper()
            if s == "T":
                return raw * 1e12
            elif s == "B":
                return raw * 1e9
            elif s == "M":
                return raw * 1e6
        # If raw is small (likely already in trillions from "$4.87T"), convert
        if raw < 1000:
            return raw * 1e12
        return raw

    def _format_mcap(val: float) -> str:
        """Format market cap to human-readable string."""
        if val >= 1e12:
            return f"${val/1e12:.2f}T"
        elif val >= 1e9:
            return f"${val/1e9:.2f}B"
        elif val >= 1e6:
            return f"${val/1e6:.2f}M"
        return f"${val:,.0f}"

    for field_name, text in corrected.items():
        if field_name == "risk_factors":
            texts = text
        else:
            texts = [text]

        for idx, t in enumerate(texts):
            if not t:
                continue
            for pattern, metric_key, tolerance in text_patterns:
                if metric_key not in verified:
                    continue
                true_val = verified[metric_key]
                for match in pattern.finditer(t):
                    try:
                        claimed = float(match.group(2))
                    except (ValueError, IndexError):
                        continue
                    # Skip P/E values only when followed by % (e.g. "P/E ratio of 2.5%")
                    if metric_key == "pe_ttm" and claimed < 3:
                        after_match = t[match.end():match.end()+2].strip()
                        if "%" in after_match or "percent" in after_match.lower():
                            continue
                    # Market cap: normalise suffix (T/B/M in group 3)
                    if metric_key == "market_cap":
                        suffix = None
                        try:
                            suffix = match.group(3)
                        except IndexError:
                            pass
                        claimed = _normalise_mcap(claimed, suffix)
                        cmp_true = true_val  # raw dollars from context
                    elif metric_key == "quality_percentile":
                        # Decimal-drop detection: if claimed > 1.0 and true_val <= 1.0,
                        # the LLM likely dropped the decimal (0.698 → 698)
                        if claimed > 1.0 and true_val <= 1.0:
                            if claimed >= 100:
                                claimed = claimed / 1000  # 698 → 0.698
                            elif claimed >= 10:
                                claimed = claimed / 100
                        cmp_true = true_val
                    else:
                        cmp_true = true_val
                    min_val = cmp_true * (1 - tolerance)
                    max_val = cmp_true * (1 + tolerance)
                    if min_val <= claimed <= max_val:
                        continue
                    # Correct
                    old_text = match.group(0)
                    if metric_key == "pe_ttm":
                        replacement = f"P/E {true_val:.1f}x"
                    elif metric_key == "beta":
                        replacement = f"beta {true_val:.2f}"
                    elif metric_key == "vix":
                        replacement = f"VIX {true_val:.1f}"
                    elif metric_key == "yield_10y":
                        replacement = f"10Y Yield {true_val:.2f}%"
                    elif metric_key == "cpi_yoy":
                        replacement = f"CPI {true_val:.1f}%"
                    elif metric_key == "fed_funds_rate":
                        replacement = f"Fed Funds {true_val:.2f}%"
                    elif metric_key == "hy_spread_oas":
                        replacement = f"HY spread {true_val:.0f}bps"
                    elif metric_key == "quality_percentile":
                        replacement = f"quality percentile {true_val:.3f}"
                    elif metric_key == "market_cap":
                        replacement = f"market cap {_format_mcap(true_val)}"
                    else:
                        replacement = f"{metric_key} {true_val:.1f}"
                    t = t.replace(old_text, replacement)
                    corrections.append(f"{field_name}: {metric_key} {claimed}→{true_val:.1f}")
            texts[idx] = t

        if field_name == "risk_factors":
            corrected["risk_factors"] = texts
        else:
            corrected[field_name] = texts[0]

    if corrections:
        log.info("HEAD_ANALYST metric corrections: %s", "; ".join(corrections))

    if (corrected["investment_thesis"] != response.investment_thesis or
        corrected["bull_case"] != response.bull_case or
        corrected["bear_case"] != response.bear_case or
        corrected["risk_factors"] != list(response.risk_factors)):
        return response.model_copy(update={
            "investment_thesis": corrected["investment_thesis"],
            "bull_case": corrected["bull_case"],
            "bear_case": corrected["bear_case"],
            "risk_factors": corrected["risk_factors"],
        })
    return response


def _is_ollama() -> bool:
    """Runtime Ollama detection — avoids module-level env var issues in uvicorn."""
    url = os.environ.get("ANTHROPIC_BASE_URL", "")
    return "127.0.0.1:11434" in url or "localhost:11434" in url


class ParaDebateOrchestrator:
    # Per-agent timeout (seconds) — evaluated at runtime, not import time
    # Sonnet is slower than Haiku; timeouts must accommodate 5 parallel Sonnet calls
    @property
    def SPECIALIST_TIMEOUT(self):
        return 60 if _is_ollama() else 55

    @property
    def ADVERSARIAL_TIMEOUT(self):
        return 45 if _is_ollama() else 45

    @property
    def HEAD_ANALYST_TIMEOUT(self):
        return 75 if _is_ollama() else 75

    def __init__(self):
        self._specialists = [
            MacroAgent(),
            FundamentalAgent(),
            TechnicalAgent(),
            SentimentAgent(),
            GeopoliticalAgent(),
        ]
        self._adversarial = AdversarialAgent()
        self._head = HeadAnalystAgent()

    async def analyse(
        self, ticker: str, market: str, context: dict
    ) -> AnalystResponse:
        # Step 1: run 5 specialists + 1 adversarial IN PARALLEL.
        # Adversarial uses raw context only (via run_raw) — no dependency on specialist outputs.
        # On cloud: 6 parallel API calls. On Ollama: sequential (single-threaded).
        async def _run_one(agent, timeout: float, msg_override=None):
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(agent.run, ticker, context, msg_override),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                log.warning("%s agent timed out after %ds for %s", agent.agent_name, int(timeout), ticker)
                return agent._neutral_fallback(ticker, context)
            except Exception as exc:
                log.warning("%s agent crashed for %s: %s", agent.agent_name, ticker, exc)
                return agent._neutral_fallback(ticker, context)

        if _is_ollama():
            # Ollama: sequential execution
            specialist_outputs: list[AgentOutput] = []
            for agent in self._specialists:
                try:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(agent.run_with_retry, ticker, context, 3),
                        timeout=self.SPECIALIST_TIMEOUT,
                    )
                    specialist_outputs.append(
                        result if isinstance(result, AgentOutput) else agent._neutral_fallback(ticker, context)
                    )
                except asyncio.TimeoutError:
                    log.warning("%s agent timed out after %ds for %s", agent.agent_name, int(self.SPECIALIST_TIMEOUT), ticker)
                    specialist_outputs.append(agent._neutral_fallback(ticker, context))
                except Exception as exc:
                    log.warning("%s agent crashed for %s: %s", agent.agent_name, ticker, exc)
                    specialist_outputs.append(agent._neutral_fallback(ticker, context))
            # Adversarial after specialists (Ollama, uses specialist outputs)
            adv_msg = self._adversarial._build_user_message(ticker, context)
            adversarial_output = await _run_one(self._adversarial, self.ADVERSARIAL_TIMEOUT, adv_msg)
        else:
            # Cloud: run ALL 6 agents in parallel — adversarial gets raw context
            all_agents = self._specialists + [self._adversarial]
            all_timeouts = [self.SPECIALIST_TIMEOUT] * 5 + [self.ADVERSARIAL_TIMEOUT]
            # Adversarial: raw context (no specialist outputs needed for bear thesis)
            adv_raw_msg = self._adversarial._build_user_message_raw(ticker, context)
            all_msgs = [None] * 5 + [adv_raw_msg]
            raw_results = await asyncio.gather(
                *[_run_one(a, t, m) for a, t, m in zip(all_agents, all_timeouts, all_msgs)],
            )
            specialist_outputs = [
                r if isinstance(r, AgentOutput) else agent._neutral_fallback()
                for r, agent in zip(raw_results[:5], self._specialists)
            ]
            adversarial_output = raw_results[5]
            if not isinstance(adversarial_output, AgentOutput):
                adversarial_output = self._adversarial._neutral_fallback()

        # Enforce adversarial constraint — override BULL to BEAR
        if adversarial_output.stance == "BULL":
            adversarial_output = adversarial_output.model_copy(update={"stance": "BEAR"})

        # Step 2: validate ALL agent outputs against [VERIFIED] context metrics
        specialist_outputs = [_validate_agent_metrics(o, context) for o in specialist_outputs]
        adversarial_output = _validate_agent_metrics(adversarial_output, context)

        # Step 2b: algorithmic guardrails — override LLM optimism on SEVERE red flags only
        red_flags = context.get("_fundamental_red_flags", [])
        severe_flags = [f for f in red_flags if f.startswith("SEVERE|")]
        moderate_flags = [f.replace("MODERATE|", "") for f in red_flags if f.startswith("MODERATE|")]
        if severe_flags:
            for i, o in enumerate(specialist_outputs):
                if o.agent == "FUNDAMENTAL" and o.stance in ("BULL", "NEUTRAL"):
                    flag_text = severe_flags[0].replace("SEVERE|", "")
                    log.info("Overriding FUNDAMENTAL %s→BEAR for %s: %s", o.stance, ticker, flag_text)
                    specialist_outputs[i] = o.model_copy(update={
                        "stance": "BEAR",
                        "thesis": f"ALGORITHMIC OVERRIDE — {flag_text}. {o.thesis}",
                        "key_points": [flag_text] + o.key_points[:2],
                    })

        all_outputs = specialist_outputs + [adversarial_output]

        # Step 3: compute consensus score (adversarial included with 1.5x weight)
        # Adversarial is the dedicated bear voice — weighting it higher prevents systematic BUY bias
        weighted_outputs = []
        for o in specialist_outputs:
            weighted_outputs.append((STANCE_SCORE[o.stance], CONVICTION_MULT[o.conviction]))
        # Adversarial gets 1.5x weight (was 2x — caused systematic SELL bias)
        adv_score = STANCE_SCORE[adversarial_output.stance]
        adv_conv = CONVICTION_MULT[adversarial_output.conviction]
        weighted_outputs.append((adv_score, adv_conv * 1.5))

        total_weight = sum(w for _, w in weighted_outputs)
        consensus = (
            sum(s * w for s, w in weighted_outputs) / total_weight
        ) if total_weight > 0 else 0.0

        # Step 4: HEAD ANALYST synthesis (with consensus guardrails)
        # Map consensus to expected verdict range to prevent systematic bias
        # Wider HOLD zone: ±0.35 (was ±0.25) to counter bearish drag from adversarial
        if consensus <= -0.5:
            verdict_guidance = "STRONG SELL or SELL"
        elif consensus <= -0.35:
            verdict_guidance = "SELL or HOLD"
        elif consensus <= 0.35:
            verdict_guidance = "HOLD"
        elif consensus <= 0.5:
            verdict_guidance = "HOLD or BUY"
        else:
            verdict_guidance = "BUY or STRONG BUY"

        composite_score = float(context.get("composite_score", 0.5))
        # Pass moderate red flags to HEAD ANALYST for contextual awareness
        context["_moderate_flags"] = moderate_flags
        try:
            synthesis = await asyncio.wait_for(
                asyncio.to_thread(self._head.run_synthesis, ticker, all_outputs, composite_score, context, consensus, verdict_guidance),
                timeout=self.HEAD_ANALYST_TIMEOUT,
            )
        except asyncio.TimeoutError:
            log.warning("HEAD_ANALYST timed out after %ds for %s", self.HEAD_ANALYST_TIMEOUT, ticker)
            synthesis = self._head._fallback_synthesis()

        response = AnalystResponse(
            ticker=ticker,
            head_analyst_verdict=self._clamp_verdict(synthesis["verdict"], verdict_guidance),
            investment_thesis=synthesis["investment_thesis"],
            bull_case=synthesis["bull_case"],
            bear_case=synthesis["bear_case"],
            risk_factors=synthesis["risk_factors"],
            agent_outputs=all_outputs,
            consensus_score=round(consensus, 3),
        )
        # Validate HEAD_ANALYST text for metric hallucinations
        response = _validate_analyst_response_text(response, context)
        return response

    @staticmethod
    def _clamp_verdict(verdict: str, guidance: str) -> str:
        """Prevent HEAD_ANALYST from deviating 2+ tiers from consensus."""
        _TIER = {"STRONG SELL": -2, "SELL": -1, "HOLD": 0, "BUY": 1, "STRONG BUY": 2}
        _RANGE = {
            "STRONG SELL or SELL": (-2, -1),
            "SELL or HOLD": (-1, 0),
            "HOLD": (0, 0),
            "HOLD or BUY": (0, 1),
            "BUY or STRONG BUY": (1, 2),
        }
        v_tier = _TIER.get(verdict, 0)
        lo, hi = _RANGE.get(guidance, (-2, 2))
        if v_tier < lo:
            # Map back from tier to verdict string
            return next(k for k, v in _TIER.items() if v == lo)
        if v_tier > hi:
            return next(k for k, v in _TIER.items() if v == hi)
        return verdict

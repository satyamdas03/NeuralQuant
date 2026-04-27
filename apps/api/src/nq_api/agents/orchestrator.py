# apps/api/src/nq_api/agents/orchestrator.py
"""PARA-DEBATE orchestrator — runs 5 specialist agents in parallel, adversarial sequentially, HEAD ANALYST synthesises."""
from __future__ import annotations
import asyncio
import logging
import os

from nq_api.schemas import AgentOutput, AnalystResponse

log = logging.getLogger(__name__)
from nq_api.agents.macro import MacroAgent
from nq_api.agents.fundamental import FundamentalAgent
from nq_api.agents.technical import TechnicalAgent
from nq_api.agents.sentiment import SentimentAgent
from nq_api.agents.geopolitical import GeopoliticalAgent
from nq_api.agents.adversarial import AdversarialAgent
from nq_api.agents.head_analyst import HeadAnalystAgent

STANCE_SCORE = {"BULL": 1.0, "NEUTRAL": 0.5, "BEAR": 0.0}
CONVICTION_MULT = {"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4}

def _is_ollama() -> bool:
    """Runtime Ollama detection — avoids module-level env var issues in uvicorn."""
    url = os.environ.get("ANTHROPIC_BASE_URL", "")
    return "127.0.0.1:11434" in url or "localhost:11434" in url


class ParaDebateOrchestrator:
    # Per-agent timeout (seconds) — evaluated at runtime, not import time
    @property
    def SPECIALIST_TIMEOUT(self):
        return 60 if _is_ollama() else 25

    @property
    def ADVERSARIAL_TIMEOUT(self):
        return 45 if _is_ollama() else 20

    @property
    def HEAD_ANALYST_TIMEOUT(self):
        return 80 if _is_ollama() else 35

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
        # Step 1: run 5 specialists — sequentially if Ollama (can't parallelise), else parallel
        async def _run_one(agent, timeout: float):
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(agent.run, ticker, context),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                log.warning("%s agent timed out after %ds for %s", agent.agent_name, int(timeout), ticker)
                return agent._neutral_fallback()

        if _is_ollama():
            # Ollama processes one request at a time — run sequentially with retries
            specialist_outputs: list[AgentOutput] = []
            for agent in self._specialists:
                try:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(agent.run_with_retry, ticker, context, 3),
                        timeout=self.SPECIALIST_TIMEOUT,
                    )
                    specialist_outputs.append(
                        result if isinstance(result, AgentOutput) else agent._neutral_fallback()
                    )
                except asyncio.TimeoutError:
                    log.warning("%s agent timed out after %ds for %s", agent.agent_name, int(self.SPECIALIST_TIMEOUT), ticker)
                    specialist_outputs.append(agent._neutral_fallback())
        else:
            raw_results = await asyncio.gather(
                *[_run_one(a, self.SPECIALIST_TIMEOUT) for a in self._specialists],
            )
            specialist_outputs = [
                r if isinstance(r, AgentOutput)
                else agent._neutral_fallback()
                for r, agent in zip(raw_results, self._specialists)
            ]

        # Step 2: build bull thesis summary for adversarial to stress-test
        bull_summary = "; ".join(
            o.thesis for o in specialist_outputs if o.stance == "BULL"
        ) or "Mixed signals from panel."

        adversarial_context = {**context, "bull_thesis": bull_summary}
        try:
            adversarial_output = await asyncio.wait_for(
                asyncio.to_thread(self._adversarial.run, ticker, adversarial_context),
                timeout=self.ADVERSARIAL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            log.warning("ADVERSARIAL agent timed out after %ds for %s", self.ADVERSARIAL_TIMEOUT, ticker)
            adversarial_output = self._adversarial._neutral_fallback()

        # Enforce adversarial constraint — override BULL to BEAR
        # (defence against LLM disobeying its system prompt constraint)
        if adversarial_output.stance == "BULL":
            adversarial_output = adversarial_output.model_copy(update={"stance": "BEAR"})

        all_outputs = specialist_outputs + [adversarial_output]

        # Step 3: compute consensus score (adversarial excluded)
        consensus = (
            sum(
                STANCE_SCORE[o.stance] * CONVICTION_MULT[o.conviction]
                for o in specialist_outputs
            ) / len(specialist_outputs)
        ) if specialist_outputs else 0.5

        # Step 4: HEAD ANALYST synthesis
        composite_score = float(context.get("composite_score", 0.5))
        try:
            synthesis = await asyncio.wait_for(
                asyncio.to_thread(self._head.run_synthesis, ticker, all_outputs, composite_score, context),
                timeout=self.HEAD_ANALYST_TIMEOUT,
            )
        except asyncio.TimeoutError:
            log.warning("HEAD_ANALYST timed out after %ds for %s", self.HEAD_ANALYST_TIMEOUT, ticker)
            synthesis = self._head._fallback_synthesis()

        return AnalystResponse(
            ticker=ticker,
            head_analyst_verdict=synthesis["verdict"],
            investment_thesis=synthesis["investment_thesis"],
            bull_case=synthesis["bull_case"],
            bear_case=synthesis["bear_case"],
            risk_factors=synthesis["risk_factors"],
            agent_outputs=all_outputs,
            consensus_score=round(consensus, 3),
        )

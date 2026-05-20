"""LiveKit function-calling tools for deep research — PARA-DEBATE, sentiment."""

from __future__ import annotations

import json
import logging
from typing import Annotated

from livekit.agents import llm

log = logging.getLogger(__name__)


class ResearchTools(llm.FunctionContext):
    """Deep research tools — PARA-DEBATE analysis, sentiment, news."""

    @llm.ai_callable(
        description=(
            "Run a full 7-agent PARA-DEBATE analysis on a stock. This invokes 7 AI agents "
            "(Fundamental, Technical, Macro, Sentiment, Geopolitical, Adversarial, and Head Analyst) "
            "that debate the stock from all angles and produce an investment verdict with bull/bear "
            "cases and risk factors. Takes 30-60 seconds. Use ONLY when the client specifically "
            "requests deep analysis, a full research report, or wants to understand all sides "
            "of an investment thesis. For simple price checks or quick opinions, use get_stock_price instead."
        ),
    )
    async def run_para_debate(
        self,
        ticker: Annotated[
            str,
            llm.TypeInfo(description="Stock ticker symbol, e.g. 'AAPL' or 'RELIANCE'"),
        ],
        market: Annotated[
            str,
            llm.TypeInfo(description="Market: 'US' or 'IN'"),
        ] = "US",
    ) -> str:
        """Run full PARA-DEBATE analysis on a stock."""
        try:
            from nq_api.agents.orchestrator import ParaDebateOrchestrator
            from nq_api.data_builder import _fetch_one, fetch_real_macro

            # Build context
            fund = _fetch_one(ticker, market, fast_pe=True)
            if fund is None:
                return json.dumps({"status": "unavailable", "ticker": ticker, "reason": "Could not fetch fundamental data — FMP/yfinance may be unavailable"})

            macro = fetch_real_macro()
            context = {**fund.to_context_dict(), **macro}

            # Run the debate
            orch = ParaDebateOrchestrator()
            result = await orch.analyse(ticker, market, context)

            # Extract key outputs
            agent_breakdown = []
            if result.agent_outputs:
                for o in result.agent_outputs:
                    agent_breakdown.append({
                        "agent": o.agent,
                        "stance": o.stance,
                        "conviction": o.conviction,
                    })

            return json.dumps({
                "status": "ok",
                "ticker": ticker,
                "market": market,
                "verdict": result.head_analyst_verdict,
                "investment_thesis": result.investment_thesis,
                "bull_case": result.bull_case,
                "bear_case": result.bear_case,
                "risk_factors": result.risk_factors[:5],
                "consensus_score": result.consensus_score,
                "agent_breakdown": agent_breakdown,
            }, default=str)
        except Exception as exc:
            log.error("run_para_debate failed for %s/%s: %s", ticker, market, exc)
            return json.dumps({
                "status": "error",
                "ticker": ticker,
                "reason": "The deep analysis engine is temporarily unavailable — try again in a moment, or use get_stock_price for a quick overview.",
            })

    @llm.ai_callable(
        description=(
            "Get recent news sentiment for a stock. Returns sentiment score, recent headlines, "
            "and insider trading activity. Use when client asks about recent news, sentiment, "
            "or what's being said about a stock in the media."
        ),
    )
    async def get_sentiment(
        self,
        ticker: Annotated[
            str,
            llm.TypeInfo(description="Stock ticker symbol, e.g. 'AAPL' or 'RELIANCE'"),
        ],
        market: Annotated[
            str,
            llm.TypeInfo(description="Market: 'US' or 'IN'"),
        ] = "US",
    ) -> str:
        """Fetch news sentiment for a stock."""
        try:
            from nq_api.cache.score_cache import read_enrichment

            enrichment = read_enrichment(ticker, market) or {}

            return json.dumps({
                "status": "ok",
                "ticker": ticker,
                "market": market,
                "news_sentiment": enrichment.get("news_sentiment"),
                "news_sentiment_score": enrichment.get("news_sentiment_score"),
                "news_items": enrichment.get("news_items", [])[:5],
                "insider_cluster_score": enrichment.get("insider_cluster_score"),
                "insider_net_buy_ratio": enrichment.get("insider_net_buy_ratio"),
                "short_interest_pct": enrichment.get("short_interest_pct"),
            }, default=str)
        except Exception as exc:
            log.error("get_sentiment failed for %s: %s", ticker, exc)
            return json.dumps({"status": "error", "reason": str(exc)})

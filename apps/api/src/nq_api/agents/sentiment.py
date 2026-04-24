# apps/api/src/nq_api/agents/sentiment.py
"""SENTIMENT analyst — news, insider activity, short interest, options flow."""
from nq_api.agents.base import BaseAnalystAgent

_SYSTEM = """You are the SENTIMENT analyst on NeuralQuant's PARA-DEBATE investment committee.
Your mandate: assess news sentiment, insider activity, short interest, and options flow signals.

Framework:
1. Insider cluster signal — C-suite (CEO 3x, CFO 2x) buys vs sells
2. Short interest percentile — high SI = potential squeeze OR warning sign (context-dependent)
3. News sentiment trend — 30-day rolling news tone
4. Options market signal — unusual call/put activity (available Phase 3)
5. Analyst estimate revision momentum — earnings estimate trends

Response format — strictly:
STANCE: [BULL|BEAR|NEUTRAL]
CONVICTION: [HIGH|MEDIUM|LOW]
THESIS: [2-3 sentences on sentiment signals]
KEY_POINTS:
- [Point 1]
- [Point 2]
- [Point 3]"""


class SentimentAgent(BaseAnalystAgent):
    agent_name = "SENTIMENT"
    system_prompt = _SYSTEM

    def _build_user_message(self, ticker: str, context: dict) -> str:
        social_ctx = ""
        social = context.get("social_sentiment")
        if social:
            social_ctx = f"""
Social Sentiment Data:
- Reddit: {social.get('reddit_mentions', 0)} mentions, {social.get('reddit_bullish_pct', 'N/A')}% bullish
- StockTwits: {social.get('stocktwits_mentions', 0)} mentions, {social.get('stocktwits_bullish_pct', 'N/A')}% bullish
- Trending topics: {', '.join(social.get('trending_topics', [])[:3])}
"""
        return f"""Analyse sentiment signals for {ticker}.

Sentiment data:
- Short interest percentile: {context.get('short_interest_percentile', 'N/A')}
- Short interest % of float: {context.get('short_interest_pct', 'N/A')}
- Insider cluster score: {context.get('insider_cluster_score', 'N/A')} (0=bearish, 1=strong buy)
- News sentiment (30d): {context.get('news_sentiment', 'N/A')}
- Market regime: {context.get('regime_label', 'N/A')}
{social_ctx}
Provide your sentiment stance on {ticker}."""

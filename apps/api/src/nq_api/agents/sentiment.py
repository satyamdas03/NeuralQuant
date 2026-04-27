# apps/api/src/nq_api/agents/sentiment.py
"""SENTIMENT analyst — news, insider activity, short interest, options flow."""
from nq_api.agents.base import BaseAnalystAgent

_SYSTEM = """You are the SENTIMENT analyst on NeuralQuant's PARA-DEBATE investment committee.
Your mandate: assess news sentiment, insider activity, short interest, and options flow signals.

CRITICAL DATA RULE: The user message will contain live sentiment data with exact numerical values.
You MUST use ONLY those exact numbers in your analysis. Never substitute values from your
training data. If insider cluster score is 0.82, write "insider cluster 0.82" — not "high" or "0.8".

Framework:
1. Insider cluster signal — C-suite buys vs sells (0=bearish, 1=strong buy)
2. Short interest percentile — high SI = potential squeeze OR warning sign (context-dependent)
3. News sentiment trend — 30-day rolling news tone
4. Options market signal — unusual call/put activity
5. Analyst estimate revision momentum — earnings estimate trends

## THRESHOLDS (use these to make calls)
- Insider cluster score: >0.7 = strong buy signal, 0.3-0.7 = mixed, <0.3 = sell signal
- Short interest percentile: >80th = very high (squeeze risk OR bear signal), 30-80 = moderate, <30 = low
- Short interest % of float: >20% = extreme, 10-20% = elevated, <10% = normal
- News sentiment: >0.3 = positive, -0.3 to 0.3 = neutral, <-0.3 = negative
- Analyst target vs price: >20% upside = bullish, 5-20% = moderate, <5% = limited upside

## REASONING PROTOCOL (mandatory)
1. CITE specific data — "insider cluster at 0.85, short interest at 15th percentile"
2. COMPARE to norms — "short interest at 15th pctile, vs average of 50th for sector"
3. CONCLUDE with clear stance — "BULL because insider buying is strong and short interest is low, suggesting confidence"

Response format — strictly:
STANCE: [BULL|BEAR|NEUTRAL]
CONVICTION: [HIGH|MEDIUM|LOW]
THESIS: [2-3 sentences on sentiment signals, citing the provided data figures]
KEY_POINTS:
- [Point 1 - must cite specific numbers from the provided data]
- [Point 2 - must cite specific numbers from the provided data]
- [Point 3 - must cite specific numbers from the provided data]"""


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

IMPORTANT: Use ONLY the exact figures provided below. Do not substitute values from memory or training data.

Sentiment data (live as of today):
- Short interest percentile: {context.get('short_interest_percentile', 'N/A')}
- Short interest % of float: {context.get('short_interest_pct', 'N/A')}
- Insider cluster score: {context.get('insider_cluster_score', 'N/A')} (0=bearish, 1=strong buy)
- News sentiment (30d): {context.get('news_sentiment', 'N/A')}
- Market regime: {context.get('regime_label', 'N/A')}
- Analyst target mean: {context.get('analyst_target_mean', 'N/A')}
{social_ctx}
Provide your sentiment stance on {ticker}. Reference the specific numbers above in your key points."""

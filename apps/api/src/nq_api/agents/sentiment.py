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
3. News sentiment — Finnhub sentiment label/score + buzz metrics
4. Options market signal — unusual call/put activity
5. Analyst estimate revision momentum — earnings estimate trends

## THRESHOLDS (use these to make calls)
- Insider cluster score: >0.7 = strong buy signal, 0.3-0.7 = mixed, <0.3 = sell signal
- Insider net buy ratio: >0.6 = net buying (bullish), 0.4-0.6 = balanced, <0.4 = net selling (bearish)
- Short interest percentile: >80th = very high (squeeze risk OR bear signal), 30-80 = moderate, <30 = low
- Short interest % of float: >20% = extreme, 10-20% = elevated, <10% = normal
- News sentiment: bullish = positive, neutral = mixed, bearish = negative
- News buzz: >1.0 = elevated coverage, 0.5-1.0 = normal, <0.5 = low coverage
- Analyst target vs price: >20% upside = bullish, 5-20% = moderate, <5% = limited upside

## REASONING PROTOCOL (mandatory)
1. CITE specific data — "insider cluster at 0.85, net buy ratio 0.72, short interest at 15th percentile"
2. COMPARE to norms — "short interest at 15th pctile, vs average of 50th for sector"
3. CONCLUDE with clear stance — "BULL because insider buying is strong, news bullish, and short interest is low" or "BEAR because insider cluster below 0.3, news bearish, and short interest above 80th percentile"

Response format — strictly:
STANCE: [BULL|BEAR|NEUTRAL]
CONVICTION: [HIGH|MEDIUM|LOW]
THESIS: [2-3 sentences on sentiment signals, citing the provided data figures]
KEY_POINTS:
- [Point 1 - must cite specific numbers from the provided data]
- [Point 2 - must cite specific numbers from the provided data]
- [Point 3 - must cite specific numbers from the provided data]

You must be equally willing to output BEAR as BULL — if insider selling or high short interest dominates, say BEAR.

LIMITED DATA PROTOCOL: When enrichment data is sparse (e.g., insider_cluster_score near 0.5, news_sentiment N/A, few data points available), you MUST still produce a definitive stance. Use the data that IS present. A NEUTRAL/LOW stance based on limited real data is MORE valuable than a NEUTRAL/LOW stance based on no data. State clearly: "Based on limited available data..." and proceed with your best assessment using whatever signals are present. Never default to NEUTRAL/LOW simply because data is incomplete."""


class SentimentAgent(BaseAnalystAgent):
    agent_name = "SENTIMENT"
    system_prompt = _SYSTEM

    def _build_user_message(self, ticker: str, context: dict) -> str:
        # Insider data — Finnhub enrichment
        insider_score = context.get("insider_cluster_score", 0.5)
        insider_summary = context.get("insider_summary", "")
        insider_net_buy = context.get("insider_net_buy_ratio")

        # News sentiment — Finnhub enrichment
        news_label = context.get("news_sentiment", "N/A")
        news_score = context.get("news_sentiment_score", "N/A")
        news_buzz = context.get("news_buzz", "N/A")

        # Social sentiment (if available)
        social_ctx = ""
        social = context.get("social_sentiment")
        if social:
            social_ctx = f"""
Social Sentiment Data:
- Reddit: {social.get('reddit_mentions', 0)} mentions, {social.get('reddit_bullish_pct', 'N/A')}% bullish
- StockTwits: {social.get('stocktwits_mentions', 0)} mentions, {social.get('stocktwits_bullish_pct', 'N/A')}% bullish
- Trending topics: {', '.join(social.get('trending_topics', [])[:3])}
"""
        # Build insider context line
        insider_ctx = f"- Insider cluster score: {insider_score} (0=bearish, 1=strong buy)"
        if insider_net_buy is not None:
            insider_ctx += f"\n- Insider net buy ratio: {insider_net_buy}"
        if insider_summary:
            insider_ctx += f"\n- Insider summary: {insider_summary}"

        # Build news sentiment context
        news_ctx = f"- News sentiment label: {news_label}"
        if news_score != "N/A":
            news_ctx += f"\n- News sentiment score: {news_score} (-1 to 1)"
        if news_buzz != "N/A":
            news_ctx += f"\n- News buzz: {news_buzz} (>1.0 = elevated coverage)"

        return f"""Analyse sentiment signals for {ticker}.

IMPORTANT: Use ONLY the exact figures provided below. Do not substitute values from memory or training data.

Sentiment data (live as of today):
- Low-short-interest rank (0-1, higher = LESS shorting = bullish): {context.get('low_short_interest_rank', 'N/A')}
- Short interest % of float: {context.get('short_interest_pct', 'N/A')}%
{insider_ctx}
{news_ctx}
- Market regime: {context.get('regime_label', 'N/A')}
- Analyst target mean: {context.get('analyst_target_mean', 'N/A')}
{social_ctx}
Provide your sentiment stance on {ticker}. Reference the specific numbers above in your key points.

CRITICAL: low_short_interest_rank is the INVERSE short interest rank — a high value (e.g. 0.86) means LOW short interest (bullish), NOT high short interest. Always cross-reference with short_interest_pct (actual % of float). Short interest >5% of float is elevated; >10% is very high."""
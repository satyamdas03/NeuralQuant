"""
Free social sentiment connectors — zero API keys required.

Sources:
  1. StockTwits public API (free, no key) — https://api.stocktwits.com/api/2/streams/symbol/{TICKER}.json
  2. yfinance news headlines + VADER as "social buzz" proxy
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


@dataclass
class SocialItem:
    ticker: str
    source: str
    bullish_pct: float | None
    mention_count: int
    top_topics: list[str]


def fetch_stocktwits_public(ticker: str) -> SocialItem | None:
    """
    Fetch sentiment from StockTwits public API.
    Completely free, no API key required.
    Rate limit: ~200 req/hr from same IP.
    """
    try:
        url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
        resp = httpx.get(url, timeout=8.0)
        if resp.status_code != 200:
            return None

        data = resp.json()
        symbol_data = data.get("symbol", {})
        messages = data.get("messages", [])

        if not messages:
            return SocialItem(
                ticker=ticker.upper(),
                source="stocktwits",
                bullish_pct=None,
                mention_count=0,
                top_topics=[],
            )

        # Count bullish/bearish from sentiment field
        bull = 0
        bear = 0
        topics: dict[str, int] = {}

        for msg in messages[:50]:
            sentiment = (msg.get("entities", {}).get("sentiment") or {}).get("basic") or ""
            if sentiment == "Bullish":
                bull += 1
            elif sentiment == "Bearish":
                bear += 1

            # Extract trending topics from message body
            body = msg.get("body", "")
            # Simple: extract hashtags as topics
            for word in body.split():
                if word.startswith("$") and len(word) > 1:
                    tag = word[1:].upper()
                    topics[tag] = topics.get(tag, 0) + 1

        total_scored = bull + bear
        bullish_pct = (bull / total_scored * 100) if total_scored > 0 else None
        mention_count = len(messages)

        # Top 5 topics
        top_topics = [t for t, _ in sorted(topics.items(), key=lambda x: -x[1])[:5]]

        logger.debug(
            "StockTwits %s: %d msgs, %d bull/%d bear, bullish_pct=%s",
            ticker, mention_count, bull, bear, bullish_pct,
        )

        return SocialItem(
            ticker=ticker.upper(),
            source="stocktwits",
            bullish_pct=bullish_pct,
            mention_count=mention_count,
            top_topics=top_topics,
        )

    except Exception as e:
        logger.debug("StockTwits public fetch failed for %s: %s", ticker, e)
        return None


def fetch_social_buzz_yfinance(ticker: str, market: str = "US") -> SocialItem | None:
    """
    Use yfinance news headlines + VADER as social buzz proxy.
    Aggregates recent news sentiment as a measure of social/media buzz.
    """
    try:
        import yfinance as yf
        yf_sym = f"{ticker.upper()}.NS" if market == "IN" else ticker.upper()
        raw_news = yf.Ticker(yf_sym).news or []

        if not raw_news:
            return SocialItem(
                ticker=ticker.upper(),
                source="social_buzz",
                bullish_pct=None,
                mention_count=0,
                top_topics=[],
            )

        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        analyzer = SentimentIntensityAnalyzer()
    except ImportError:
        return None
    except Exception as e:
        logger.debug("yfinance social buzz fetch failed for %s: %s", ticker, e)
        return None

    bull = 0
    bear = 0
    topics: dict[str, int] = {}

    for n in raw_news[:30]:
        title = (n.get("content") or {}).get("title") or n.get("title") or ""
        if not title:
            continue

        score = analyzer.polarity_scores(title)["compound"]
        if score >= 0.15:
            bull += 1
        elif score <= -0.15:
            bear += 1

        # Extract ticker mentions as topics
        for word in title.split():
            word = word.strip(".,!?:;()[]{}")
            if word.startswith("$") and len(word) > 1 and len(word) <= 6:
                topics[word[1:].upper()] = topics.get(word[1:].upper(), 0) + 1

    total_scored = bull + bear
    bullish_pct = (bull / total_scored * 100) if total_scored > 0 else None
    mention_count = len(raw_news)

    top_topics = sorted(topics, key=lambda t: -topics[t])[:5]

    logger.debug(
        "SocialBuzz %s: %d headlines, %d bull/%d bear, bullish_pct=%s",
        ticker, mention_count, bull, bear, bullish_pct,
    )

    return SocialItem(
        ticker=ticker.upper(),
        source="social_buzz",
        bullish_pct=bullish_pct,
        mention_count=mention_count,
        top_topics=top_topics,
    )


def fetch_all_free(tickers: list[str], market: str = "US") -> list[SocialItem]:
    """
    Fetch social sentiment for multiple tickers using only free sources.
    Priority: StockTwits → yfinance social buzz.

    Rate limited: max 30 tickers, 1s delay between StockTwits calls.
    """
    items: list[SocialItem] = []
    for i, t in enumerate(tickers[:30]):
        # StockTwits (public, free)
        st = fetch_stocktwits_public(t)
        if st and st.bullish_pct is not None:
            items.append(st)
        else:
            # Fallback: yfinance headlines as social buzz
            buzz = fetch_social_buzz_yfinance(t, market)
            if buzz and buzz.bullish_pct is not None:
                items.append(buzz)
            else:
                # Empty item so UI knows we tried
                items.append(SocialItem(
                    ticker=t.upper(),
                    source="social_buzz",
                    bullish_pct=None,
                    mention_count=0,
                    top_topics=[],
                ))

        # Rate limit: be gentle with StockTwits public API
        if i < len(tickers) - 1:
            time.sleep(0.5)

    return items

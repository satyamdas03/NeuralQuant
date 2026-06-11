"""
Free social sentiment connectors — zero API keys required.

Source: yfinance news headlines + VADER as a "social buzz" proxy.
(StockTwits connector removed — their public API returns 403 for all
symbols since 2025; see bug 125.)
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SocialItem:
    ticker: str
    source: str
    bullish_pct: float | None
    mention_count: int
    top_topics: list[str]


def fetch_social_buzz_yfinance(ticker: str, market: str = "US") -> SocialItem | None:
    """
    Use yfinance news headlines + VADER as social buzz proxy.
    Aggregates recent news sentiment as a measure of social/media buzz.
    """
    try:
        from nq_data.price.yf_guard import news as yf_news
        raw_news = yf_news(ticker, market)

        if raw_news is None:
            return None  # guard skipped (Render) or yfinance failed

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
        title = n.get("title") or ""
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
    Rate limited: max 30 tickers, 0.5s delay between calls.
    """
    items: list[SocialItem] = []
    for i, t in enumerate(tickers[:30]):
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

        if i < len(tickers) - 1:
            time.sleep(0.5)

    return items

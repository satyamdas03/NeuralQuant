"""Sentiment endpoint (Pillar C).

Aggregates VADER sentiment over recent news headlines for a ticker.
Pulls headlines from yfinance Ticker.news (free, no API key).
"""
from __future__ import annotations
from typing import Any
import asyncio
import logging

from fastapi import APIRouter, HTTPException

router = APIRouter()
log = logging.getLogger(__name__)

# Tiny lexicon-based fallback so we don't hard-depend on vaderSentiment install.
# We do try vaderSentiment first (much more accurate); fall back on ImportError.
_POS = {"beat", "beats", "surge", "surges", "rally", "record", "gain", "gains",
        "strong", "upgrade", "upgrades", "profit", "profits", "boom", "soar",
        "soars", "rise", "rises", "jump", "jumps", "bullish", "outperform",
        "exceed", "exceeds", "growth", "expand", "expands", "positive"}
_NEG = {"miss", "misses", "plunge", "plunges", "crash", "crashes", "fall",
        "falls", "weak", "downgrade", "downgrades", "loss", "losses", "fear",
        "recession", "drop", "drops", "decline", "declines", "bearish",
        "underperform", "lawsuit", "probe", "fraud", "warn", "warns", "cut",
        "cuts", "layoff", "layoffs", "negative"}


def _vader_score(text: str) -> float:
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore
        return float(SentimentIntensityAnalyzer().polarity_scores(text)["compound"])
    except ImportError:
        toks = {t.strip(".,!?:;").lower() for t in text.split()}
        p = len(toks & _POS)
        n = len(toks & _NEG)
        total = p + n
        if total == 0:
            return 0.0
        return (p - n) / total


def _label(score: float) -> str:
    if score >= 0.25:
        return "Bullish"
    if score <= -0.25:
        return "Bearish"
    return "Neutral"


@router.get("/news/{ticker}")
async def get_sentiment(ticker: str, market: str = "US", limit: int = 15) -> dict[str, Any]:
    """Compute aggregate news sentiment for a ticker."""
    return await asyncio.to_thread(_get_sentiment_sync, ticker, market, limit)


def _get_sentiment_sync(ticker: str, market: str, limit: int) -> dict[str, Any]:
    """Blocking sentiment compute — runs in thread pool."""
    try:
        import yfinance as yf
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"yfinance missing: {e}")

    t = ticker.upper()
    yf_symbol = f"{t}.NS" if market == "IN" else t
    try:
        raw_news = yf.Ticker(yf_symbol).news or []
    except Exception as exc:
        log.warning("yfinance news fetch failed for %s: %s", yf_symbol, exc)
        raw_news = []

    items = []
    scores: list[float] = []
    for n in raw_news[:limit]:
        # yfinance shape changes over versions; normalize.
        title = (n.get("content") or {}).get("title") or n.get("title") or ""
        url = (
            (n.get("content") or {}).get("canonicalUrl", {}).get("url")
            if isinstance(n.get("content"), dict)
            else n.get("link")
        ) or ""
        publisher = (n.get("content") or {}).get("provider", {}).get("displayName") or n.get("publisher") or ""
        if not title:
            continue
        s = _vader_score(title)
        scores.append(s)
        items.append({"title": title, "url": url, "publisher": publisher, "score": round(s, 3)})

    agg = sum(scores) / len(scores) if scores else 0.0
    return {
        "ticker": t,
        "market": market,
        "aggregate_score": round(agg, 3),
        "label": _label(agg),
        "n_headlines": len(items),
        "headlines": items,
    }


# ---------- Social Sentiment Endpoints ----------
# Uses StockTwits public API (free, no key) + yfinance news aggregation as social buzz.
# Reddit/StockTwits premium connectors replaced with free alternatives.

from nq_data.social_free import fetch_stocktwits_public, fetch_social_buzz_yfinance, fetch_all_free


@router.get("/social")
async def get_social_sentiment_all(tickers: str = "AAPL,MSFT,GOOGL,TSLA,NVDA") -> dict[str, Any]:
    """Return aggregated social sentiment for top tickers using free sources (StockTwits + yfinance news)."""
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]

    # Fetch live from free sources in thread pool
    items = await asyncio.to_thread(fetch_all_free, ticker_list, "US")

    results = []
    for item in items:
        results.append({
            "ticker": item.ticker,
            "stocktwits_bullish_pct": item.bullish_pct if item.source == "stocktwits" else None,
            "stocktwits_mentions": item.mention_count if item.source == "stocktwits" else 0,
            "social_buzz_bullish_pct": item.bullish_pct if item.source == "social_buzz" else None,
            "social_buzz_mentions": item.mention_count if item.source == "social_buzz" else 0,
            "source": item.source,
            "topics": item.top_topics,
        })

    return {"tickers": results, "count": len(results)}


@router.get("/social/{ticker}")
async def get_social_sentiment_ticker(ticker: str, market: str = "US") -> dict[str, Any]:
    """Return social sentiment for a specific ticker using free sources."""
    t = ticker.upper()

    # Try StockTwits first, fall back to yfinance social buzz
    st_item = await asyncio.to_thread(fetch_stocktwits_public, t)

    if st_item and st_item.bullish_pct is not None:
        return {
            "ticker": t,
            "stocktwits": {
                "bullish_pct": st_item.bullish_pct,
                "mentions": st_item.mention_count,
                "topics": st_item.top_topics,
            },
            "social_buzz": None,
            "source": "stocktwits",
            "cached": False,
        }

    # Fallback to yfinance social buzz
    buzz_item = await asyncio.to_thread(fetch_social_buzz_yfinance, t, market)
    if buzz_item and buzz_item.bullish_pct is not None:
        return {
            "ticker": t,
            "stocktwits": None,
            "social_buzz": {
                "bullish_pct": buzz_item.bullish_pct,
                "mentions": buzz_item.mention_count,
                "topics": buzz_item.top_topics,
            },
            "source": "social_buzz",
            "cached": False,
        }

    return {
        "ticker": t,
        "stocktwits": None,
        "social_buzz": None,
        "source": "unavailable",
        "cached": False,
        "loading": True,
    }

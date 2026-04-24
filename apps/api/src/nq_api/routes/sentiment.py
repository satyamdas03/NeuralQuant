"""Sentiment endpoint (Pillar C).

Aggregates VADER sentiment over recent news headlines for a ticker.
Pulls headlines from yfinance Ticker.news (free, no API key).
"""
from __future__ import annotations
from typing import Any
import json
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


@router.get("/{ticker}")
def get_sentiment(ticker: str, market: str = "US", limit: int = 15) -> dict[str, Any]:
    """Compute aggregate news sentiment for a ticker."""
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

from nq_data.social import RedditConnector, StockTwitsConnector
from nq_data.store import DataStore

_social_store: DataStore | None = None


def _get_social_store() -> DataStore:
    global _social_store
    if _social_store is None:
        _social_store = DataStore()
    return _social_store


def _fetch_social(tickers: list[str]) -> dict[str, Any]:
    """Fetch social sentiment from cache or live sources."""
    store = _get_social_store()
    reddit = RedditConnector()
    st = StockTwitsConnector()

    # Fetch fresh data
    reddit_items = reddit.fetch(tickers)
    st_items = st.fetch(tickers)

    # Upsert into cache
    all_items = reddit_items + st_items
    if all_items:
        store.upsert_social_sentiment(all_items)

    # Aggregate by ticker
    agg: dict[str, dict] = {}
    for item in all_items:
        t = item.ticker
        if t not in agg:
            agg[t] = {"reddit_bullish_pct": None, "reddit_mentions": 0,
                      "stocktwits_bullish_pct": None, "stocktwits_mentions": 0,
                      "total_mentions": 0, "topics": []}
        if item.source == "reddit":
            agg[t]["reddit_bullish_pct"] = item.bullish_pct
            agg[t]["reddit_mentions"] = item.mention_count
        elif item.source == "stocktwits":
            agg[t]["stocktwits_bullish_pct"] = item.bullish_pct
            agg[t]["stocktwits_mentions"] = item.mention_count
        agg[t]["total_mentions"] += item.mention_count
        for topic in item.top_topics:
            if topic not in agg[t]["topics"]:
                agg[t]["topics"].append(topic)

    return agg


@router.get("/social")
def get_social_sentiment_all(tickers: str = "AAPL,MSFT,GOOGL,TSLA,NVDA") -> dict[str, Any]:
    """Return aggregated social sentiment for top tickers."""
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    agg = _fetch_social(ticker_list)
    results = []
    for t, data in agg.items():
        results.append({
            "ticker": t,
            **data,
            "topics": data["topics"][:5],
        })
    return {"tickers": results, "count": len(results)}


@router.get("/social/{ticker}")
def get_social_sentiment_ticker(ticker: str) -> dict[str, Any]:
    """Return social sentiment for a specific ticker."""
    t = ticker.upper()
    store = _get_social_store()

    # Check cache first (4-hour TTL)
    cached = store.get_social_sentiment(t, max_age_hours=4)
    if cached:
        reddit_data = None
        st_data = None
        for row in cached:
            source = row[1]
            if source == "reddit":
                reddit_data = row
            elif source == "stocktwits":
                st_data = row
        return {
            "ticker": t,
            "reddit": {
                "bullish_pct": reddit_data[2] if reddit_data else None,
                "mentions": reddit_data[3] if reddit_data else 0,
                "topics": json.loads(reddit_data[4]) if reddit_data and reddit_data[4] else [],
            } if reddit_data else None,
            "stocktwits": {
                "bullish_pct": st_data[2] if st_data else None,
                "mentions": st_data[3] if st_data else 0,
                "topics": json.loads(st_data[4]) if st_data and st_data[4] else [],
            } if st_data else None,
            "cached": True,
        }

    # Fresh fetch if no cache
    agg = _fetch_social([t])
    if t not in agg:
        return {"ticker": t, "reddit": None, "stocktwits": None, "cached": False}

    data = agg[t]
    return {
        "ticker": t,
        "reddit": {
            "bullish_pct": data.get("reddit_bullish_pct"),
            "mentions": data.get("reddit_mentions", 0),
            "topics": [t for t in data.get("topics", [])[:5]],
        } if data.get("reddit_bullish_pct") is not None else None,
        "stocktwits": {
            "bullish_pct": data.get("stocktwits_bullish_pct"),
            "mentions": data.get("stocktwits_mentions", 0),
            "topics": [t for t in data.get("topics", [])[:5]],
        } if data.get("stocktwits_bullish_pct") is not None else None,
        "cached": False,
    }

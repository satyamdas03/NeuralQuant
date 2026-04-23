"""GET /news — enriched NewsDesk feed.

Aggregates live headlines from Yahoo Finance (via yfinance) across US broad-market
(^GSPC) and India mega-caps, enriches each item with category, sentiment and
related tickers, and surfaces trending topics.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

router = APIRouter()
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sentiment (same lexicon as sentiment.py for consistency)
# ---------------------------------------------------------------------------
_POS = {
    "beat", "beats", "surge", "surges", "rally", "record", "gain", "gains",
    "strong", "upgrade", "upgrades", "profit", "profits", "boom", "soar",
    "soars", "rise", "rises", "jump", "jumps", "bullish", "outperform",
    "exceed", "exceeds", "growth", "expand", "expands", "positive",
}
_NEG = {
    "miss", "misses", "plunge", "plunges", "crash", "crashes", "fall",
    "falls", "weak", "downgrade", "downgrades", "loss", "losses", "fear",
    "recession", "drop", "drops", "decline", "declines", "bearish",
    "underperform", "lawsuit", "probe", "fraud", "warn", "warns", "cut",
    "cuts", "layoff", "layoffs", "negative", "sell", "selling",
}


def _sentiment_score(text: str) -> float:
    toks = {t.strip(".,!?:;\"'()[]").lower() for t in text.split()}
    p = len(toks & _POS)
    n = len(toks & _NEG)
    total = p + n
    if total == 0:
        return 0.0
    return (p - n) / total


def _sentiment_label(score: float) -> str:
    if score >= 0.25:
        return "bullish"
    if score <= -0.25:
        return "bearish"
    return "neutral"


# ---------------------------------------------------------------------------
# Categorisation & ticker extraction
# ---------------------------------------------------------------------------
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "india": [
        "india", "indian", "nifty", "sensex", "nse", "bse", "reliance",
        "tcs", "infosys", "hdfc", "kotak", "wipro", "tata", "adani",
        "lic", "sbi", "axis bank", "icici", "bajaj", "larsen", "ltim",
    ],
    "earnings": [
        "earnings", "revenue", "profit", "eps", "quarterly", "quarter",
        "results", "outlook", "guidance", "forecast", "beat", "miss",
        "dividend", "buyback", "ebitda", "margin", "sales",
    ],
    "insider": [
        "insider", "ceo", "cfo", "coo", "officer", "director", "form 4",
        "sells", "sold", "buys", "bought", "stake", "acquisition", "merger",
        "takeover", "holding", "holdings", "beneficial owner",
    ],
    "macro": [
        "fed", "fed funds", "rate hike", "rate cut", "interest rate",
        "gdp", "inflation", "recession", "oil", "treasury", "yield",
        "macro", "economy", "jobs", "unemployment", "cpi", "ppi",
        "geopolitical", "war", "sanctions", "trade", "tariff", "budget",
    ],
}

_KNOWN_TICKERS: dict[str, str] = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "nvidia": "NVDA",
    "meta": "META",
    "tesla": "TSLA",
    "berkshire": "BRK-B",
    "jpmorgan": "JPM",
    "visa": "V",
    "mastercard": "MA",
    "unitedhealth": "UNH",
    "exxon": "XOM",
    "johnson": "JNJ",
    "home depot": "HD",
    "costco": "COST",
    "abbvie": "ABBV",
    "lilly": "LLY",
    "chevron": "CVX",
    "bank of america": "BAC",
    "netflix": "NFLX",
    "oracle": "ORCL",
    "adobe": "ADBE",
    "salesforce": "CRM",
    "amd": "AMD",
    "broadcom": "AVGO",
    "walmart": "WMT",
    "mcdonald": "MCD",
    "pfizer": "PFE",
    "intuitive": "ISRG",
    "palantir": "PLTR",
    "reliance": "RELIANCE.NS",
    "tcs": "TCS.NS",
    "infosys": "INFY.NS",
    "hdfc": "HDFCBANK.NS",
    "kotak": "KOTAKBANK.NS",
    "wipro": "WIPRO.NS",
    "tata power": "TATAPOWER.NS",
    "spy": "SPY",
    "qqq": "QQQ",
    "tlt": "TLT",
    "uso": "USO",
    "xle": "XLE",
    "india": "INDA",
    "epi": "EPI",
    "mindx": "MINDX",
}

_STOP_WORDS = {
    "the", "to", "of", "a", "in", "for", "on", "and", "with", "at", "by",
    "from", "as", "is", "are", "was", "were", "be", "been", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should", "may",
    "might", "can", "shall", "said", "says", "say", "up", "down", "over",
    "after", "before", "into", "out", "more", "less", "than", "about", "its",
    "his", "her", "their", "an", "this", "that", "these", "those", "i", "you",
    "he", "she", "it", "we", "they", "us", "them", "my", "your", "our", "all",
    "no", "not", "but", "or", "so", "if", "then", "just", "only", "also",
    "new", "next", "last", "first", "between", "among", "through", "during",
    "above", "below", "off", "near", "per", "vs", "ago", "now", "today",
    "year", "years", "month", "months", "week", "day", "days", "time",
    "times", "company", "companies", "firm", "firms", "stock", "stocks",
    "market", "markets", "share", "shares", "price", "prices", "bn", "mln",
    "billion", "million", "thousand", "pct", "percent", "report", "reports",
    "according", "source", "sources", "people", "person", "group", "plans",
    "plan", "expected", "expect", "sees", "seen", "due", "set", "amid",
    "despite", "following", "because", "while", "during", "since", "until",
    "both", "either", "neither", "whether", "how", "what", "when", "where",
    "who", "why", "which", "way", "big", "small", "large", "high", "low",
    "good", "bad", "best", "worst", "better", "worse", "long", "short",
    "late", "early", "old", "young", "major", "minor", "local", "global",
    "national", "international", "public", "private", "general", "specific",
    "total", "full", "part", "whole", "half", "quarter", "third", "top",
    "back", "front", "side", "end", "start", "point", "place", "area",
    "region", "state", "city", "country", "world", "government", "president",
    "minister", "official", "chief", "head", "leader", "member", "partnership",
    "unit", "division", "segment", "business", "industry", "sector", "deal",
}


def _category(title: str) -> str:
    t = title.lower()
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in t for kw in keywords):
            return cat
    return "us_markets"


def _extract_tickers(title: str) -> list[str]:
    t = title.lower()
    found: list[str] = []
    for word, ticker in _KNOWN_TICKERS.items():
        if word in t and ticker not in found:
            found.append(ticker)
    # Supplement with raw uppercase candidates that look like tickers
    for candidate in re.findall(r"\b[A-Z]{1,5}\b", title):
        if candidate in found:
            continue
        if candidate in {
            "CEO", "CFO", "COO", "THE", "FOR", "AND", "NEW", "YORK", "SEC",
            "IPO", "ETF", "AI", "GDP", "EPS", "Q1", "Q2", "Q3", "Q4", "USA",
            "US", "UK", "EU", "UN", "FBI", "CIA", "IRS", "FDA", "FTC",
            "DOJ", "PCE", "CPI", "PPI", "ISM", "PMI", "OPEC", "NATO",
            "WSJ", "CNBC", "BBC", "CNN", "Benzinga", "Reuters", "Bloomberg",
            "AP", "UP", "DOWN", "LEFT", "RIGHT", "TRUE", "FALSE", "YES", "NO",
            "BUY", "SELL", "HOLD", "LONG", "SHORT", "CALL", "PUT", "VIX",
            "SPY", "QQQ", "TLT", "USO", "XLE", "INDA", "EPI",
        }:
            continue
        found.append(candidate)
    return found[:5]


# ---------------------------------------------------------------------------
# Time formatting
# ---------------------------------------------------------------------------
def _relative_time(ts: int | str | None) -> str:
    if ts is None or ts == "":
        return ""
    try:
        if isinstance(ts, int):
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        elif isinstance(ts, str):
            if ts.isdigit():
                dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            else:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            return str(ts)
        now = datetime.now(dt.tzinfo)
        diff = now - dt
        seconds = diff.total_seconds()
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            return f"{int(seconds // 60)}m ago"
        if seconds < 86400:
            return f"{int(seconds // 3600)}h ago"
        if seconds < 604800:
            return f"{int(seconds // 86400)}d ago"
        return dt.strftime("%b %d")
    except Exception:
        return str(ts)


# ---------------------------------------------------------------------------
# Yahoo Finance fetch (blocking -> called via asyncio.to_thread)
# ---------------------------------------------------------------------------
def _fetch_yf_news(ticker: str, limit: int = 10) -> list[dict[str, Any]]:
    try:
        import yfinance as yf  # type: ignore
        items = yf.Ticker(ticker).news or []
        result = []
        for item in items[:limit]:
            content = item.get("content") or {}
            title = content.get("title") or item.get("title", "")
            publisher = (
                (content.get("provider") or {}).get("displayName")
                or item.get("publisher", "")
            )
            url = (
                (content.get("canonicalUrl") or {}).get("url")
                or item.get("link", "")
            )
            pub_date = content.get("pubDate") or item.get("providerPublishTime")
            if title:
                result.append(
                    {
                        "title": title,
                        "publisher": publisher,
                        "url": url,
                        "time": pub_date,
                    }
                )
        return result
    except Exception as exc:
        log.warning("yfinance news fetch failed for %s: %s", ticker, exc)
        return []


# ---------------------------------------------------------------------------
# Trending topics
# ---------------------------------------------------------------------------
def _compute_trending(headlines: list[dict[str, Any]]) -> list[str]:
    words: list[str] = []
    for h in headlines:
        title_lower = h["title"].lower()
        # Named-entity / ticker tokens first
        for word, ticker in _KNOWN_TICKERS.items():
            if word in title_lower and ticker not in words:
                words.append(ticker)
        # Then raw words
        for w in re.findall(r"[A-Za-z]+", h["title"]):
            wl = w.lower()
            if len(wl) > 2 and wl not in _STOP_WORDS:
                words.append(wl)
    counts = Counter(words)
    return [word for word, _ in counts.most_common(12)][:8]


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
_news_cache: dict[str, Any] | None = None
_news_ts: float = 0.0
NEWS_TTL = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------
@router.get("/news")
async def get_news_desk(n: int = 20) -> dict[str, Any]:
    """Return enriched NewsDesk headlines, overall sentiment and trending topics."""
    global _news_cache, _news_ts
    if _news_cache and time.time() - _news_ts < NEWS_TTL:
        return _news_cache

    # Pull from several broad-market / mega-cap tickers in parallel
    sources = ["^GSPC", "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS"]
    raw_batches = await asyncio.gather(
        *[asyncio.to_thread(_fetch_yf_news, sym, 8) for sym in sources]
    )

    seen: set[str] = set()
    enriched: list[dict[str, Any]] = []
    for batch in raw_batches:
        for item in batch:
            title = item.get("title", "")
            if not title or title in seen:
                continue
            seen.add(title)
            score = _sentiment_score(title)
            enriched.append(
                {
                    "title": title,
                    "publisher": item.get("publisher", ""),
                    "url": item.get("url", ""),
                    "time": _relative_time(item.get("time")),
                    "category": _category(title),
                    "tickers": _extract_tickers(title),
                    "sentiment": _sentiment_label(score),
                    "_score": score,
                }
            )

    # Sort by recency (yfinance already returns roughly newest-first) and cap
    headlines = enriched[:n]

    # Overall desk sentiment
    if headlines:
        avg = sum(h["_score"] for h in headlines) / len(headlines)
        overall = (
            "bullish" if avg >= 0.25 else "bearish" if avg <= -0.25 else "neutral"
        )
    else:
        overall = "neutral"

    # Strip internal field before returning
    for h in headlines:
        h.pop("_score", None)

    trending = _compute_trending(headlines)

    result = {
        "sentiment": overall,
        "headlines": headlines,
        "trending": trending,
    }
    _news_cache = result
    _news_ts = time.time()
    return result

"""Reddit sentiment connector — uses public JSON API (no auth required)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import httpx

from ..broker import broker
from ..models import SocialSentiment

log = logging.getLogger(__name__)

SUBREDDITS = ["wallstreetbets", "stocks", "investing", "IndiaInvestments", "nse"]
_TICKER_RE = re.compile(r"\b[A-Z]{1,5}(?:\.NS)?\b")
_POS_WORDS = frozenset({"bullish", "buy", "long", "moon", "rocket", "calls", "up", "gain", "surge", "breakout"})
_NEG_WORDS = frozenset({"bearish", "sell", "short", "put", "crash", "dump", "down", "loss", "plunge", "dead"})


class RedditConnector:
    """Fetch ticker mentions and sentiment from Reddit via public JSON API."""

    def __init__(self):
        self._client = httpx.Client(timeout=20.0, follow_redirects=True)

    def fetch(self, tickers: list[str], limit_per_sub: int = 10) -> list[SocialSentiment]:
        results: dict[str, dict] = {}
        for sub in SUBREDDITS:
            with broker.acquire("reddit"):
                try:
                    url = f"https://www.reddit.com/r/{sub}/hot.json?limit={limit_per_sub}"
                    resp = self._client.get(url, headers={"User-Agent": "NeuralQuant/1.0"})
                    if resp.status_code != 200:
                        log.warning("Reddit r/%s returned %d", sub, resp.status_code)
                        continue
                    posts = resp.json().get("data", {}).get("children", [])
                    for post in posts:
                        d = post.get("data", {})
                        title = d.get("title", "")
                        score = d.get("score", 0)
                        mentioned = _TICKER_RE.findall(title.upper())
                        title_lower = title.lower()
                        is_bullish = any(w in title_lower for w in _POS_WORDS)
                        is_bearish = any(w in title_lower for w in _NEG_WORDS)
                        for t in mentioned:
                            if t not in tickers and f"{t}.NS" not in tickers:
                                continue
                            key = t if t in tickers else t.replace(".NS", "")
                            if key not in results:
                                results[key] = {"mentions": 0, "bullish": 0, "topics": []}
                            results[key]["mentions"] += 1
                            if is_bullish:
                                results[key]["bullish"] += 1
                            topic = title[:60] + "..." if len(title) > 60 else title
                            if topic not in results[key]["topics"][:5]:
                                results[key]["topics"].append(topic)
                except Exception as exc:
                    log.warning("Reddit r/%s fetch error: %s", sub, exc)
                    continue

        now = datetime.now(timezone.utc)
        items = []
        for ticker, data in results.items():
            if data["mentions"] == 0:
                continue
            items.append(SocialSentiment(
                ticker=ticker,
                source="reddit",
                bullish_pct=round(data["bullish"] / data["mentions"] * 100, 1),
                mention_count=data["mentions"],
                top_topics=data["topics"][:5],
                fetched_at=now,
            ))
        return items
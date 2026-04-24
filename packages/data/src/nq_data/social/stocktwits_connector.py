"""StockTwits sentiment connector — uses public API (no auth required for basic access)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from ..broker import broker
from ..models import SocialSentiment

log = logging.getLogger(__name__)


class StockTwitsConnector:
    """Fetch ticker sentiment from StockTwits public API."""

    def __init__(self):
        self._client = httpx.Client(timeout=15.0, follow_redirects=True)

    def fetch(self, tickers: list[str]) -> list[SocialSentiment]:
        results: list[SocialSentiment] = []
        now = datetime.now(timezone.utc)

        for ticker in tickers[:20]:
            with broker.acquire("stocktwits"):
                try:
                    symbol = ticker.replace(".NS", "")
                    url = f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json?limit=30"
                    resp = self._client.get(url)
                    if resp.status_code != 200:
                        log.debug("StockTwits %s returned %d", symbol, resp.status_code)
                        continue
                    data = resp.json()
                    messages = data.get("messages", [])
                    if not messages:
                        continue

                    bullish = 0
                    bearish = 0
                    total = len(messages)
                    topics: list[str] = []

                    for msg in messages:
                        body = msg.get("body", "").lower()
                        sentiment = msg.get("entities", {}).get("sentiment", {})
                        if sentiment:
                            basic = sentiment.get("basic", "")
                            if basic == "Bullish":
                                bullish += 1
                            elif basic == "Bearish":
                                bearish += 1
                        else:
                            if any(w in body for w in ("buy", "long", "bull", "up", "calls")):
                                bullish += 1
                            elif any(w in body for w in ("sell", "short", "bear", "down", "puts")):
                                bearish += 1

                        if len(topics) < 5:
                            text = msg.get("body", "")[:80]
                            if text and text not in topics:
                                topics.append(text)

                    bullish_pct = round(bullish / max(bullish + bearish, 1) * 100, 1) if (bullish + bearish) > 0 else 50.0

                    results.append(SocialSentiment(
                        ticker=ticker,
                        source="stocktwits",
                        bullish_pct=bullish_pct,
                        mention_count=total,
                        top_topics=topics[:5],
                        fetched_at=now,
                    ))
                except Exception as exc:
                    log.warning("StockTwits %s error: %s", ticker, exc)
                    continue

        return results
"""News → Classification pipeline orchestrator.

Async orchestration layer: fetches headlines from Finnhub + StockTwits + Reddit,
deduplicates, batch-classifies via Claude, stores to Supabase.

Follows newsdesk.py async pattern: asyncio.gather + asyncio.to_thread.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

MAX_HEADLINES_PER_SOURCE = 8
MAX_TICKERS = 30


async def ingest_headlines(
    tickers: list[str],
    market: str = "US",
    max_per_source: int = MAX_HEADLINES_PER_SOURCE,
) -> list[tuple[str, str, str, str | None]]:
    """Fetch headlines from all sources in parallel. Returns deduplicated list.

    Returns: list of (ticker, headline_text, source_name, published_at) tuples.
    Deduplication: case-insensitive match on first 60 chars of headline.
    """
    tickers = tickers[:MAX_TICKERS]
    if market == "IN":
        suffixes = [".NS", ".BO"]
        resolved = []
        for t in tickers:
            resolved.append(t)
            if "." not in t:
                resolved = [f"{x}{suffixes[0]}" for x in tickers]
    else:
        resolved = list(tickers)

    results: list[tuple[str, str, str, str | None]] = []
    seen: set[str] = set()

    # Fetch in parallel: Finnhub news per ticker + social batch
    async def _fetch_all():
        tasks = []

        # Finnhub per-ticker news (fast, free tier)
        for ticker in tickers:
            tasks.append(asyncio.to_thread(_fetch_finnhub_headlines, ticker))

        # StockTwits batch (public API, no key needed)
        tasks.append(asyncio.to_thread(_fetch_social_headlines, tickers))

        raw_batches = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=25.0,
        )
        return raw_batches

    raw_batches = await _fetch_all()

    for raw in raw_batches:
        if isinstance(raw, Exception):
            logger.warning("Headline fetch error: %s", raw)
            continue
        if not raw:
            continue
        for item in raw:
            headline = item[1] if isinstance(item, tuple) else item.get("headline", "")
            key = headline.strip().lower()[:60]
            if not key or key in seen:
                continue
            seen.add(key)
            results.append(item if isinstance(item, tuple) else (
                item.get("ticker", ""),
                item.get("headline", ""),
                item.get("source", "unknown"),
                item.get("published_at"),
            ))

    logger.info("Headline ingest: %d tickers → %d deduped headlines", len(tickers), len(results))
    return results


def _fetch_finnhub_headlines(ticker: str) -> list[tuple[str, str, str, str | None]]:
    """Fetch Finnhub news for one ticker. Returns (ticker, headline, source, published_at) list."""
    try:
        from nq_data.finnhub import get_finnhub_client
        client = get_finnhub_client()
        news = client.get_news(ticker, days=3)
        if not news:
            return []
        return [
            (ticker, item.get("title") or item.get("summary", ""),
             "finnhub", item.get("published_at"))
            for item in news[:MAX_HEADLINES_PER_SOURCE]
            if item.get("title") or item.get("summary")
        ]
    except Exception as exc:
        logger.debug("Finnhub fetch failed for %s: %s", ticker, exc)
        return []


def _fetch_social_headlines(tickers: list[str]) -> list[tuple[str, str, str, str | None]]:
    """Fetch StockTwits + yfinance social buzz for a batch of tickers."""
    items = []
    try:
        from nq_data.social_free import fetch_all_free
        social_data = fetch_all_free(list(tickers))
        if social_data:
            for s in social_data:
                if not hasattr(s, 'top_topics') or not s.top_topics:
                    continue
                ticker = getattr(s, 'ticker', '')
                for topic in s.top_topics[:3]:
                    items.append((
                        ticker,
                        f"Trending: {topic} (bullish {getattr(s, 'bullish_pct', 0):.0f}%)",
                        getattr(s, 'source', 'stocktwits'),
                        None,
                    ))
    except Exception as exc:
        logger.debug("Social fetch failed: %s", exc)
    return items


async def run_classification_pipeline(
    tickers: list[str],
    market: str = "US",
) -> dict[str, Any]:
    """Full pipeline: ingest headlines → classify → store.

    Returns dict with pipeline results suitable for API response.
    """
    from nq_data.classifier import classify_headlines, ClassificationBatch

    t0 = datetime.now(timezone.utc)

    # Step 1: Ingest headlines from all sources
    headlines = await ingest_headlines(tickers, market)

    if not headlines:
        return {
            "status": "empty",
            "headlines_found": 0,
            "classified": 0,
            "error": None,
        }

    # Step 2: Batch classify via Claude
    batch = await asyncio.to_thread(classify_headlines, headlines)
    classified_count = len(batch.items) if batch else 0

    # Step 3: Store to Supabase
    if batch and batch.items:
        try:
            await asyncio.to_thread(_store_to_supabase, batch.items)
        except Exception as exc:
            logger.warning("Supabase store failed (non-fatal): %s", exc)

    elapsed_ms = (datetime.now(timezone.utc) - t0).total_seconds() * 1000

    bullish = sum(1 for c in (batch.items if batch else []) if c.direction == "bullish")
    bearish = sum(1 for c in (batch.items if batch else []) if c.direction == "bearish")
    neutral = sum(1 for c in (batch.items if batch else []) if c.direction == "neutral")

    return {
        "status": "ok" if classified_count > 0 else "no_classifications",
        "headlines_found": len(headlines),
        "classified": classified_count,
        "bullish": bullish,
        "bearish": bearish,
        "neutral": neutral,
        "latency_ms": round(elapsed_ms, 0),
        "model": batch.model_used if batch else "",
        "tokens": batch.tokens_used if batch else 0,
        "error": None,
    }


def _store_to_supabase(classifications: list) -> int:
    """Write classified headlines to Supabase news_classifications table."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        logger.warning("Supabase config missing — skipping news_classifications store")
        return 0

    import httpx

    rows = []
    now = datetime.now(timezone.utc).isoformat()
    for c in classifications:
        rows.append({
            "ticker": c.ticker,
            "headline": c.headline,
            "source": c.source,
            "published_at": c.published_at,
            "direction": c.direction,
            "materiality": c.materiality,
            "confidence": c.confidence,
            "rationale": c.rationale,
            "classified_at": now,
        })

    written = 0
    for i in range(0, len(rows), 50):
        chunk = rows[i : i + 50]
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.post(
                    f"{url}/rest/v1/news_classifications",
                    json=chunk,
                    headers={
                        "apikey": key,
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=minimal",
                    },
                )
                if r.status_code in (200, 201):
                    written += len(chunk)
                else:
                    # 409 = duplicate (UNIQUE constraint on ticker,headline)
                    if r.status_code != 409:
                        logger.warning("Supabase insert returned %d: %s", r.status_code, r.text[:200])
        except Exception as exc:
            logger.warning("Supabase insert failed: %s", exc)

    logger.info("Stored %d/%d news classifications to Supabase", written, len(rows))
    return written

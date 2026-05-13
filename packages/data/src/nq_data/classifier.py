"""Claude batch headline classifier — bullish/bearish/neutral + materiality score.

Follows Polymarket Pipeline pattern: batch 15 headlines per LLM call,
single prompt with structured JSON output. Costs ~$0.02 per batch.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

BATCH_SIZE = 15
DEFAULT_MODEL = "claude-sonnet-4-6"


@dataclass
class ClassifiedNews:
    ticker: str
    headline: str
    source: str
    published_at: str | None
    direction: str  # bullish, bearish, neutral
    materiality: float  # 0-1
    confidence: float  # 0-1
    rationale: str


@dataclass
class ClassificationBatch:
    items: list[ClassifiedNews] = field(default_factory=list)
    model_used: str = ""
    tokens_used: int = 0
    latency_ms: float = 0.0


SYSTEM_PROMPT = """You are a financial news classifier. For each headline, classify:
- direction: "bullish" (positive for stock price), "bearish" (negative), or "neutral"
- materiality: 0-1 score for how much this news should move the stock (0=no impact, 1=major catalyst)
- rationale: one short sentence explaining classification

Return ONLY valid JSON array. No other text. Format:
[{"ticker": "AAPL", "direction": "bullish", "materiality": 0.7, "rationale": "..."}]

Materiality calibration:
- 0.0-0.2: noise, general market commentary, minor mentions
- 0.2-0.4: company-specific news, moderate competitive developments
- 0.4-0.6: earnings updates, product announcements, analyst changes
- 0.6-0.8: significant beats/misses, M&A rumors, regulatory actions, major partnerships
- 0.8-1.0: blockbuster events: FDA approvals, major acquisitions, fraud allegations, CEO departures"""


def classify_headlines(
    ticker_headlines: list[tuple[str, str, str, str | None]],
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
) -> ClassificationBatch:
    """Classify headlines via Claude batch prompt.

    Args:
        ticker_headlines: list of (ticker, headline, source, published_at) tuples
        api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        model: Claude model to use

    Returns ClassificationBatch with all classified headlines.
    Malformed JSON or classification failures return neutral direction + 0 materiality.
    """
    import anthropic

    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        logger.warning("No Anthropic API key — classification skipped")
        return ClassificationBatch()

    results: list[ClassifiedNews] = []
    total_tokens = 0
    t0 = datetime.now(timezone.utc)

    for i in range(0, len(ticker_headlines), BATCH_SIZE):
        batch = ticker_headlines[i : i + BATCH_SIZE]
        headlines_json = json.dumps([
            {"id": j, "ticker": t, "headline": h, "source": s}
            for j, (t, h, s, _) in enumerate(batch)
        ])

        user_msg = f"Classify these financial news headlines:\n{headlines_json}"

        try:
            client = anthropic.Anthropic(api_key=key, timeout=30.0)
            resp = client.messages.create(
                model=model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            total_tokens += resp.usage.input_tokens + resp.usage.output_tokens if resp.usage else 0

            text = resp.content[0].text if resp.content else ""
            parsed = _parse_response(text, batch)

            for item in parsed:
                results.append(item)

        except json.JSONDecodeError as exc:
            logger.warning("Classifier JSON parse error: %s", exc)
            for t, h, s, p in batch:
                results.append(_neutral_result(t, h, s, p, "JSON parse error"))
        except Exception as exc:
            logger.warning("Classifier API error: %s", exc)
            for t, h, s, p in batch:
                results.append(_neutral_result(t, h, s, p, str(exc)))

    elapsed = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
    return ClassificationBatch(
        items=results,
        model_used=model,
        tokens_used=total_tokens,
        latency_ms=elapsed,
    )


def _parse_response(text: str, batch: list) -> list[ClassifiedNews]:
    """Parse Claude JSON response, matching items back to ticker by index."""
    data = json.loads(text)
    if not isinstance(data, list):
        # Sometimes Claude wraps in {"items": [...]} or extra keys
        if isinstance(data, dict):
            data = data.get("items") or data.get("classifications") or data.get("results") or [data]
        else:
            data = [data]

    results = []
    for item in data:
        idx = item.get("id", -1)
        if 0 <= idx < len(batch):
            t, h, s, p = batch[idx]
        else:
            t = item.get("ticker", "UNKNOWN")
            h = item.get("headline", "")
            s = item.get("source", "unknown")
            p = item.get("published_at")

        direction = str(item.get("direction", "neutral")).lower()
        if direction not in ("bullish", "bearish", "neutral"):
            direction = "neutral"

        materiality = max(0.0, min(1.0, float(item.get("materiality", 0.0) or 0.0)))
        confidence = max(0.0, min(1.0, float(item.get("confidence", 0.5) or 0.5)))

        results.append(ClassifiedNews(
            ticker=t,
            headline=h,
            source=s,
            published_at=p,
            direction=direction,
            materiality=materiality,
            confidence=confidence,
            rationale=str(item.get("rationale", "")),
        ))
    return results


def _neutral_result(ticker: str, headline: str, source: str, published_at: str | None, reason: str) -> ClassifiedNews:
    return ClassifiedNews(
        ticker=ticker,
        headline=headline,
        source=source,
        published_at=published_at,
        direction="neutral",
        materiality=0.0,
        confidence=0.0,
        rationale=f"Classification failed: {reason[:80]}",
    )

"""Finnhub data connector — technical indicators, news sentiment, insider data.

Free tier: 60 calls/min, US + India (NSE) supported.
Rate limiting via nq_data.broker. In-process dict cache with TTLs.
"""
from __future__ import annotations

import logging
import math
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

import httpx

from .broker import broker

log = logging.getLogger(__name__)

# ── TTLs (seconds) ──────────────────────────────────────────────────────────
_TTLS: dict[str, int] = {
    "quote": 300,        # 5 min
    "indicator": 900,    # 15 min
    "candle": 900,       # 15 min
    "news": 1800,        # 30 min
    "insider": 3600,     # 1 hour
    "news_sentiment": 1800,  # 30 min
}


class FinnhubClient:
    """Finnhub API client with rate limiting and in-process caching."""

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get("FINNHUB_API_KEY", "")
        self._client = httpx.Client(timeout=20.0, follow_redirects=True)
        self._cache: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self._enabled = bool(self._api_key)

    # ── Public API ──────────────────────────────────────────────────────────

    def get_quote(self, ticker: str) -> dict | None:
        """Real-time quote: c=current, h=high, l=low, o=open, pc=prev_close."""
        return self._fetch("quote", ticker, {"symbol": self._resolve_symbol(ticker)})

    def get_indicators(self, ticker: str) -> dict | None:
        """Compute RSI-14, MACD, ATR-14, SMA-50, SMA-200, volume from candles."""
        cached = self._cache_get("indicator", ticker)
        if cached is not None:
            return cached

        candles = self.get_candles(ticker, resolution="D", days=250)
        if not candles or len(candles) < 50:
            return None

        closes = [c["close"] for c in candles if c.get("close")]
        highs = [c["high"] for c in candles if c.get("high")]
        lows = [c["low"] for c in candles if c.get("low")]
        volumes = [c["volume"] for c in candles if c.get("volume") is not None]

        if len(closes) < 50:
            return None

        indicators: dict[str, Any] = {}

        # RSI-14
        rsi = _compute_rsi(closes, 14)
        if rsi is not None:
            indicators["rsi_14"] = round(rsi, 2)

        # MACD (12, 26, 9)
        macd_line, macd_signal, macd_hist = _compute_macd(closes)
        if macd_line is not None:
            indicators["macd_line"] = round(macd_line, 4)
        if macd_signal is not None:
            indicators["macd_signal"] = round(macd_signal, 4)
        if macd_hist is not None:
            indicators["macd_hist"] = round(macd_hist, 4)

        # ATR-14
        atr = _compute_atr(highs, lows, closes, 14)
        if atr is not None:
            indicators["atr_14"] = round(atr, 4)

        # SMA
        if len(closes) >= 50:
            indicators["sma_50"] = round(sum(closes[-50:]) / 50, 4)
        if len(closes) >= 200:
            indicators["sma_200"] = round(sum(closes[-200:]) / 200, 4)

        # Volume
        if volumes:
            indicators["volume_today"] = volumes[-1]
            avg20 = volumes[-20:] if len(volumes) >= 20 else volumes
            indicators["volume_20d_avg"] = round(sum(avg20) / len(avg20), 2)
            if indicators["volume_20d_avg"] > 0:
                indicators["volume_ratio"] = round(
                    indicators["volume_today"] / indicators["volume_20d_avg"], 3
                )

        # Price vs SMA
        price = closes[-1]
        if indicators.get("sma_50"):
            indicators["price_vs_sma50"] = round(price / indicators["sma_50"] - 1, 4)
        if indicators.get("sma_200"):
            indicators["price_vs_sma200"] = round(price / indicators["sma_200"] - 1, 4)

        indicators["current_price"] = price

        self._cache_set("indicator", ticker, indicators)
        return indicators

    def get_candles(
        self, ticker: str, resolution: str = "D", days: int = 200
    ) -> list[dict] | None:
        """Historical OHLCV candles. Tries Finnhub first, falls back to yfinance."""
        # Try Finnhub API first
        candles = self._fetch_candles_finnhub(ticker, resolution, days)
        if candles:
            return candles
        # Fallback: yfinance (free, no API key needed)
        return self._fetch_candles_yfinance(ticker, days)

    def _fetch_candles_finnhub(
        self, ticker: str, resolution: str = "D", days: int = 200
    ) -> list[dict] | None:
        """Fetch candles from Finnhub API (requires premium for stock/candle)."""
        now = int(time.time())
        fr = now - days * 86400
        params = {
            "symbol": self._resolve_symbol(ticker),
            "resolution": resolution,
            "from": str(fr),
            "to": str(now),
        }
        data = self._fetch("candle", ticker, params, cache_category="candle")
        if not data or data.get("s") != "ok":
            return None
        keys = data.get("t", [])
        closes = data.get("c", [])
        highs = data.get("h", [])
        lows = data.get("l", [])
        opens = data.get("o", [])
        vols = data.get("v", [])
        if not closes:
            return None
        return [
            {
                "timestamp": t,
                "open": o,
                "high": h,
                "low": lo,
                "close": c,
                "volume": v,
            }
            for t, o, h, lo, c, v in zip(keys, opens, highs, lows, closes, vols)
        ]

    def _fetch_candles_yfinance(
        self, ticker: str, days: int = 250
    ) -> list[dict] | None:
        """Fetch OHLCV from yfinance as free fallback for candles."""
        try:
            import yfinance as yf
            with broker.acquire("yfinance"):
                df = yf.download(
                    self._resolve_symbol(ticker),
                    period=f"{days}d",
                    interval="1d",
                    progress=False,
                    auto_adjust=True,
                    timeout=15,
                )
            if df is None or df.empty or len(df) < 50:
                log.warning("yfinance returned %d rows for %s (need 50+)", len(df) if df is not None else 0, ticker)
                return None
            # Handle MultiIndex columns from yfinance (ticker name as level 0)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            candles = []
            for idx, row in df.iterrows():
                candles.append({
                    "timestamp": int(idx.timestamp()),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                })
            log.info("yfinance OHLCV for %s: %d candles", ticker, len(candles))
            return candles
        except Exception as exc:
            log.warning("yfinance OHLCV failed for %s: %s", ticker, exc)
            return None

    def get_news(self, ticker: str, days: int = 7) -> list[dict] | None:
        """Company news with summaries."""
        from_ts = int(time.time()) - days * 86400
        to_ts = int(time.time())
        params = {
            "symbol": self._resolve_symbol(ticker),
            "from": _ts_to_date(from_ts),
            "to": _ts_to_date(to_ts),
        }
        data = self._fetch("news", ticker, params)
        if not data or not isinstance(data, list):
            return None
        return [
            {
                "title": a.get("headline", ""),
                "summary": a.get("summary", ""),
                "source": a.get("source", ""),
                "url": a.get("url", ""),
                "published_at": datetime.fromtimestamp(a.get("datetime", 0), tz=timezone.utc),
                "image": a.get("image", ""),
                "sentiment_score": None,  # Finnhub free tier doesn't include per-article sentiment
            }
            for a in data[:10]
            if a.get("headline")
        ]

    def get_insider_sentiment(self, ticker: str) -> dict | None:
        """Insider sentiment. Tries Finnhub first, falls back to SEC EDGAR."""
        # Try Finnhub API
        result = self._fetch_insider_finnhub(ticker)
        if result:
            return result
        # Fallback: SEC EDGAR Form 4 (free, no API key)
        return self._fetch_insider_edgar(ticker)

    def _fetch_insider_finnhub(self, ticker: str) -> dict | None:
        """Fetch insider sentiment from Finnhub API (premium)."""
        params = {"symbol": self._resolve_symbol(ticker)}
        data = self._fetch("insider_sentiment", ticker, params, cache_category="insider")
        if not data or not isinstance(data, dict):
            return None

        months = data.get("data", [])
        if not months:
            return None

        # Aggregate recent months
        recent = months[-6:] if len(months) >= 6 else months
        total_buy = sum(m.get("buy", 0) for m in recent)
        total_sell = sum(m.get("sell", 0) for m in recent)
        total = total_buy + total_sell

        net_buy_ratio = round(total_buy / max(total, 1), 2)
        cluster_score = _insider_cluster_score(recent)

        return {
            "net_buy_ratio": net_buy_ratio,
            "cluster_score": cluster_score,
            "recent_months": len(recent),
            "total_buy": total_buy,
            "total_sell": total_sell,
            "summary": _insider_summary(ticker, total_buy, total_sell, len(recent)),
        }

    def _fetch_insider_edgar(self, ticker: str) -> dict | None:
        """Compute insider sentiment from SEC EDGAR Form 4 (free, but slow).

        Only used as a fallback when Finnhub premium is unavailable.
        EDGAR requests can take 10-30s — suitable for background jobs,
        not for real-time per-request calls.
        """
        try:
            from .alt_signals.edgar_form4 import Form4Connector, compute_insider_cluster_score
            from datetime import date, timedelta
            end = date.today()
            start = end - timedelta(days=90)
            connector = Form4Connector()
            with broker.acquire("edgar"):
                events = connector.get_insider_events(ticker, start, end)
            if not events:
                return None
            total_buy = sum(1 for e in events if e.get("is_purchase"))
            total_sell = len(events) - total_buy
            total = total_buy + total_sell
            net_buy_ratio = round(total_buy / max(total, 1), 2)
            cluster_score = compute_insider_cluster_score(events)
            return {
                "net_buy_ratio": net_buy_ratio,
                "cluster_score": cluster_score,
                "recent_months": 3,
                "total_buy": total_buy,
                "total_sell": total_sell,
                "summary": _insider_summary(ticker, total_buy, total_sell, 3),
            }
        except Exception as exc:
            log.warning("EDGAR insider fallback failed for %s: %s", ticker, exc)
            return None

    def get_news_sentiment(self, ticker: str) -> dict | None:
        """News sentiment (buzz, bearish/neutral/bullish %). Tries Finnhub first, falls back to local NLP."""
        # Try Finnhub API
        result = self._fetch_news_sentiment_finnhub(ticker)
        if result:
            return result
        # Fallback: yfinance headlines + FinBERT/VADER
        return self._fetch_news_sentiment_local(ticker)

    def _fetch_news_sentiment_finnhub(self, ticker: str) -> dict | None:
        """Fetch news sentiment from Finnhub API (premium)."""
        params = {"symbol": self._resolve_symbol(ticker)}
        data = self._fetch("news_sentiment", ticker, params, cache_category="news_sentiment")
        if not data or not isinstance(data, dict):
            return None

        buzz = data.get("buzz", {})
        sentiment = data.get("sentiment", {})

        if not buzz and not sentiment:
            return None

        bearish = sentiment.get("bearishPercent", 0)
        bullish = sentiment.get("bullishPercent", 0)

        if bullish > 0.55:
            label = "bullish"
        elif bearish > 0.55:
            label = "bearish"
        else:
            label = "neutral"

        score = bullish - bearish

        return {
            "buzz_score": buzz.get("buzz", 0),
            "weekly_average": buzz.get("weeklyAverage", 0),
            "bearish_pct": round(bearish, 4),
            "bullish_pct": round(bullish, 4),
            "sentiment_label": label,
            "sentiment_score": round(score, 4),
            "articles_this_week": buzz.get("articlesThisWeek", 0),
            "articles_last_week": buzz.get("articlesLastWeek", 0),
        }

    def _fetch_news_sentiment_local(self, ticker: str) -> dict | None:
        """Compute news sentiment locally using yfinance headlines + VADER/FinBERT."""
        try:
            import yfinance as yf
            with broker.acquire("yfinance"):
                stock = yf.Ticker(self._resolve_symbol(ticker))
                raw_news = stock.news or []
            if not raw_news:
                log.info("No yfinance news for %s", ticker)
                return None

            # Extract headlines — yfinance v1.5+ uses content.title, older uses title
            headlines = []
            for a in raw_news[:10]:
                title = a.get("title", "")
                if not title and isinstance(a.get("content"), dict):
                    title = a["content"].get("title", "")
                if title:
                    headlines.append(title)
            if not headlines:
                return None

            # Try FinBERT first, fall back to VADER
            sentiments = _classify_headlines(headlines)

            pos = sum(1 for s in sentiments if s == "positive")
            neg = sum(1 for s in sentiments if s == "negative")
            neu = sum(1 for s in sentiments if s == "neutral")
            total = len(sentiments)

            bullish = pos / total if total else 0
            bearish = neg / total if total else 0
            score = bullish - bearish

            if bullish > 0.55:
                label = "bullish"
            elif bearish > 0.55:
                label = "bearish"
            else:
                label = "neutral"

            # Buzz = article count relative to average (proxy)
            buzz = round(total / 5.0, 2)  # normalize: 5 articles = buzz 1.0

            return {
                "buzz_score": buzz,
                "weekly_average": 0,
                "bearish_pct": round(bearish, 4),
                "bullish_pct": round(bullish, 4),
                "sentiment_label": label,
                "sentiment_score": round(score, 4),
                "articles_this_week": total,
                "articles_last_week": 0,
            }
        except Exception as exc:
            log.warning("Local news sentiment failed for %s: %s", ticker, exc)
            return None

    # ── Internal ────────────────────────────────────────────────────────────

    def _resolve_symbol(self, ticker: str) -> str:
        """Map NeuralQuant tickers to Finnhub symbols.

        Finnhub uses:
        - US: plain ticker (AAPL, MSFT)
        - NSE: ticker.NS (RELIANCE.NS)
        - BSE: ticker.BO
        """
        if ticker.startswith("^"):
            # Index tickers — Finnhub doesn't support most indices
            # Map common ones
            idx_map = {
                "^NSEI": "NSE:NIFTY50",
                "^NSEBANK": "NSE:NIFTY_BANK",
                "^BSESN": "BSE:SENSEX",
            }
            return idx_map.get(ticker, ticker)
        return ticker

    def _fetch(
        self,
        endpoint: str,
        ticker: str,
        params: dict,
        cache_category: str | None = None,
    ) -> Any:
        """Rate-limited fetch with caching."""
        cat = cache_category or endpoint
        cached = self._cache_get(cat, ticker)
        if cached is not None:
            return cached

        if not self._enabled:
            log.debug("Finnhub disabled (no API key)")
            return None

        url = f"{self.BASE_URL}/{endpoint}"
        params["token"] = self._api_key

        try:
            with broker.acquire("finnhub"):
                resp = self._client.get(url, params=params)

            if resp.status_code == 429:
                log.warning("Finnhub rate limited for %s/%s", endpoint, ticker)
                return None
            if resp.status_code != 200:
                log.debug("Finnhub %s/%s returned %d", endpoint, ticker, resp.status_code)
                return None

            data = resp.json()
            self._cache_set(cat, ticker, data)
            return data
        except httpx.TimeoutException:
            log.warning("Finnhub timeout for %s/%s", endpoint, ticker)
            return None
        except Exception as exc:
            log.warning("Finnhub error %s/%s: %s", endpoint, ticker, exc)
            return None

    def _cache_get(self, category: str, ticker: str) -> Any | None:
        key = f"{category}:{ticker}"
        with self._lock:
            if key in self._cache:
                ts, data = self._cache[key]
                ttl = _TTLS.get(category, 900)
                if time.monotonic() - ts < ttl:
                    return data
                del self._cache[key]
        return None

    def _cache_set(self, category: str, ticker: str, data: Any) -> None:
        key = f"{category}:{ticker}"
        with self._lock:
            self._cache[key] = (time.monotonic(), data)

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()


# ── Singleton ────────────────────────────────────────────────────────────────
_client: FinnhubClient | None = None
_client_lock = threading.Lock()


def get_finnhub_client() -> FinnhubClient:
    """Thread-safe singleton accessor. Works even without API key (uses yfinance fallbacks)."""
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is None:
            _client = FinnhubClient()
        return _client


# ── Indicator math ───────────────────────────────────────────────────────────

def _compute_rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    if avg_loss == 0:
        return 100.0

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    rs = avg_gain / max(avg_loss, 1e-10)
    return 100 - (100 / (1 + rs))


def _compute_macd(
    closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[float | None, float | None, float | None]:
    if len(closes) < slow:
        return None, None, None

    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    if ema_fast is None or ema_slow is None:
        return None, None, None

    macd_line = ema_fast[-1] - ema_slow[-1]

    # MACD line series for signal calculation
    macd_series = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_series = _ema(macd_series, signal)
    if signal_series is None:
        return macd_line, None, None

    macd_signal = signal_series[-1]
    macd_hist = macd_line - macd_signal
    return macd_line, macd_signal, macd_hist


def _ema(data: list[float], period: int) -> list[float] | None:
    if len(data) < period:
        return None
    multiplier = 2 / (period + 1)
    result = [sum(data[:period]) / period]
    for price in data[period:]:
        result.append((price - result[-1]) * multiplier + result[-1])
    return result


def _compute_atr(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14
) -> float | None:
    if len(highs) < period + 1:
        return None
    trs = []
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    if len(trs) < period:
        return None
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


# ── Insider helpers ──────────────────────────────────────────────────────────

def _insider_cluster_score(months: list[dict]) -> float:
    """Score 0–1: heavy buying → 1, heavy selling → 0, neutral → 0.5."""
    total_buy = sum(m.get("buy", 0) for m in months)
    total_sell = sum(m.get("sell", 0) for m in months)
    total = total_buy + total_sell
    if total == 0:
        return 0.5
    return round(total_buy / total, 2)


def _insider_summary(ticker: str, buy: int, sell: int, months: int) -> str:
    if buy + sell == 0:
        return f"No insider transactions in last {months} months for {ticker}"
    direction = "buying" if buy > sell else "selling"
    net = abs(buy - sell)
    return f"Insiders net {direction} ${net:,} in last {months} months for {ticker}"


# ── News sentiment classification ────────────────────────────────────────────

_nlp_pipeline = None
_nlp_lock = threading.Lock()
_nlp_attempted = False  # Only try FinBERT once, then fall back permanently


def _classify_headlines(headlines: list[str]) -> list[str]:
    """Classify headlines as positive/negative/neutral. Tries FinBERT, falls back to VADER."""
    global _nlp_pipeline, _nlp_attempted
    if not headlines:
        return []

    # Try FinBERT once (skip in cloud/low-memory environments)
    if not _nlp_attempted:
        _nlp_attempted = True
        try:
            import os
            # Skip FinBERT on Render/Docker (512MB RAM) — use VADER instead
            if os.environ.get("RENDER") or os.environ.get("DYNO"):
                log.info("Skipping FinBERT in cloud environment — using VADER")
            else:
                with _nlp_lock:
                    if _nlp_pipeline is None:
                        from transformers import pipeline as hf_pipeline
                        _nlp_pipeline = hf_pipeline(
                            "sentiment-analysis",
                            model="ProsusAI/finbert",
                            top_k=None,
                        )
                        log.info("FinBERT loaded for news sentiment")
        except Exception as exc:
            log.info("FinBERT not available (%s) — using VADER", exc)
            _nlp_pipeline = False  # sentinel: don't retry

    if _nlp_pipeline and _nlp_pipeline is not False:
        try:
            results = _nlp_pipeline(headlines)
            labels = []
            for r in results:
                if isinstance(r, list):
                    best = max(r, key=lambda x: x["score"])
                    label = best["label"].lower()
                else:
                    label = r["label"].lower()
                labels.append(label)
            return labels
        except Exception as exc:
            log.warning("FinBERT inference failed: %s — falling back to VADER", exc)

    # Fallback: VADER (lightweight, no model download)
    return _classify_headlines_vader(headlines)


def _classify_headlines_vader(headlines: list[str]) -> list[str]:
    """VADER-based sentiment classification as lightweight fallback."""
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        analyzer = SentimentIntensityAnalyzer()
        labels = []
        for h in headlines:
            score = analyzer.polarity_scores(h)["compound"]
            if score >= 0.05:
                labels.append("positive")
            elif score <= -0.05:
                labels.append("negative")
            else:
                labels.append("neutral")
        return labels
    except ImportError:
        # Ultimate fallback: keyword heuristics
        log.warning("VADER not available — using keyword heuristics for sentiment")
        BULL = {"surge", "beat", "rise", "gain", "record", "high", "bullish", "rally",
                "upgrade", "buy", "growth", "profit", "strong", "exceed", "jump", "soar"}
        BEAR = {"fall", "drop", "miss", "decline", "loss", "low", "bearish", "sell",
                "cut", "downgrade", "crash", "recall", "risk", "weak", "slump", "tumble"}
        labels = []
        for h in headlines:
            words = set(h.lower().split())
            b = len(words & BULL)
            s = len(words & BEAR)
            if b > s + 1:
                labels.append("positive")
            elif s > b + 1:
                labels.append("negative")
            else:
                labels.append("neutral")
        return labels


# ── Date helpers ─────────────────────────────────────────────────────────────

def _ts_to_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
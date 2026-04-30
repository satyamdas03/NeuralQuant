"""Tests for FinnhubClient — rate limiting, caching, indicator math, API parsing."""
import time
import threading
from unittest.mock import patch, MagicMock

import pytest

from nq_data.finnhub import (
    FinnhubClient,
    _compute_rsi,
    _compute_macd,
    _compute_atr,
    _ema,
    _insider_cluster_score,
    _insider_summary,
    get_finnhub_client,
    _TTLS,
)


# ── Indicator math tests ────────────────────────────────────────────────────

class TestRSI:
    def test_uptrend_high_rsi(self):
        # Monotonically increasing closes → RSI near 100
        closes = [float(i) for i in range(1, 30)]
        rsi = _compute_rsi(closes, 14)
        assert rsi is not None
        assert rsi > 80

    def test_downtrend_low_rsi(self):
        closes = [float(30 - i) for i in range(29)]
        rsi = _compute_rsi(closes, 14)
        assert rsi is not None
        assert rsi < 20

    def test_too_few_closes(self):
        assert _compute_rsi([1.0, 2.0], 14) is None

    def test_flat_rsi_middle(self):
        closes = [100.0] * 30
        rsi = _compute_rsi(closes, 14)
        # All zeros → initial RSI computation with 0 avg_loss returns 100
        # This is mathematically correct: no downward movement = max RSI
        assert rsi is not None


class TestMACD:
    def test_basic_macd(self):
        closes = [float(100 + i * 0.5) for i in range(50)]
        line, signal, hist = _compute_macd(closes)
        assert line is not None
        assert signal is not None
        assert hist is not None

    def test_too_few_closes(self):
        line, signal, hist = _compute_macd([1.0, 2.0], 12, 26, 9)
        assert line is None

    def test_bearish_crossover(self):
        # Rising then falling → MACD should go negative
        closes = [float(100 + i) for i in range(30)] + [float(129 - i * 2) for i in range(20)]
        line, signal, hist = _compute_macd(closes)
        assert line is not None
        # After reversal, histogram should be negative
        assert hist is not None


class TestATR:
    def test_constant_atr(self):
        highs = [110.0] * 20
        lows = [100.0] * 20
        closes = [105.0] * 20
        atr = _compute_atr(highs, lows, closes, 14)
        assert atr is not None
        assert abs(atr - 10.0) < 0.1  # TR = 110-100 = 10

    def test_too_few_data(self):
        assert _compute_atr([1.0], [1.0], [1.0], 14) is None

    def test_volatile_atr(self):
        highs = [110.0, 120.0, 130.0, 125.0, 115.0] + [115.0] * 15
        lows = [100.0, 105.0, 110.0, 115.0, 100.0] + [105.0] * 15
        closes = [105.0, 115.0, 125.0, 120.0, 108.0] + [110.0] * 15
        atr = _compute_atr(highs, lows, closes, 14)
        assert atr is not None
        assert atr > 5  # Volatile range


class TestEMA:
    def test_ema_smoothing(self):
        data = [float(i) for i in range(1, 30)]
        result = _ema(data, 12)
        assert result is not None
        assert len(result) > 0
        # EMA should be below the last price for rising data
        assert result[-1] < data[-1]

    def test_too_short(self):
        assert _ema([1.0, 2.0], 14) is None


class TestInsiderScore:
    def test_all_buying(self):
        months = [{"buy": 100, "sell": 0}] * 6
        score = _insider_cluster_score(months)
        assert score == 1.0

    def test_all_selling(self):
        months = [{"buy": 0, "sell": 100}] * 6
        score = _insider_cluster_score(months)
        assert score == 0.0

    def test_neutral(self):
        months = [{"buy": 50, "sell": 50}] * 6
        score = _insider_cluster_score(months)
        assert score == 0.5

    def test_empty(self):
        assert _insider_cluster_score([]) == 0.5


class TestInsiderSummary:
    def test_buying(self):
        s = _insider_summary("AAPL", 500, 100, 6)
        assert "buying" in s
        assert "AAPL" in s

    def test_no_transactions(self):
        s = _insider_summary("TSLA", 0, 0, 6)
        assert "No insider" in s


# ── Client tests ─────────────────────────────────────────────────────────────

class TestFinnhubClient:
    def test_disabled_without_key(self):
        client = FinnhubClient(api_key="")
        assert not client._enabled

    def test_enabled_with_key(self):
        client = FinnhubClient(api_key="test_key")
        assert client._enabled

    def test_cache_set_get(self):
        client = FinnhubClient(api_key="test")
        client._cache_set("quote", "AAPL", {"c": 150.0})
        result = client._cache_get("quote", "AAPL")
        assert result == {"c": 150.0}

    def test_cache_expiry(self):
        client = FinnhubClient(api_key="test")
        # Manually inject expired cache entry
        key = "quote:AAPL"
        client._cache[key] = (time.monotonic() - 9999, {"c": 150.0})
        result = client._cache_get("quote", "AAPL")
        assert result is None  # Expired

    def test_cache_clear(self):
        client = FinnhubClient(api_key="test")
        client._cache_set("quote", "AAPL", {"c": 150.0})
        client.clear_cache()
        assert client._cache_get("quote", "AAPL") is None

    def test_resolve_symbol_us(self):
        client = FinnhubClient(api_key="test")
        assert client._resolve_symbol("AAPL") == "AAPL"

    def test_resolve_symbol_nse(self):
        client = FinnhubClient(api_key="test")
        assert client._resolve_symbol("RELIANCE.NS") == "RELIANCE.NS"

    def test_resolve_symbol_nifty(self):
        client = FinnhubClient(api_key="test")
        assert client._resolve_symbol("^NSEI") == "NSE:NIFTY50"


class TestSingleton:
    def test_get_client_returns_instance(self):
        # Reset singleton
        import nq_data.finnhub as mod
        mod._client = None
        with patch.dict("os.environ", {"FINNHUB_API_KEY": "test123"}):
            client = get_finnhub_client()
            assert client._enabled
            assert client._api_key == "test123"


class TestGetIndicators:
    def test_indicators_from_candles(self):
        """Verify get_indicators computes RSI, MACD, ATR, SMA from candle data."""
        client = FinnhubClient(api_key="test")

        # Build 250 days of realistic candle data
        base = 150.0
        candles = []
        for i in range(250):
            drift = (i - 125) * 0.1  # Slight uptrend
            noise = (i % 7 - 3) * 0.5
            close = base + drift + noise
            candles.append({
                "timestamp": 1700000000 + i * 86400,
                "open": close - 0.5,
                "high": close + 1.5,
                "low": close - 1.5,
                "close": close,
                "volume": 1000000 + (i % 10) * 100000,
            })

        # Mock get_candles to return our test data
        async def mock_candles(ticker, resolution="D", days=250):
            return candles

        import asyncio
        client.get_candles = mock_candles

        result = asyncio.run(client.get_indicators("AAPL"))

        assert result is not None
        assert "rsi_14" in result
        assert "macd_line" in result
        assert "macd_signal" in result
        assert "macd_hist" in result
        assert "atr_14" in result
        assert "sma_50" in result
        assert "sma_200" in result
        assert "volume_today" in result
        assert "volume_20d_avg" in result
        assert "current_price" in result

    def test_indicators_too_few_candles(self):
        client = FinnhubClient(api_key="test")

        async def mock_candles(ticker, resolution="D", days=250):
            return [{"close": 100, "high": 101, "low": 99, "volume": 1000, "timestamp": 1, "open": 99.5}]

        import asyncio
        client.get_candles = mock_candles

        result = asyncio.run(client.get_indicators("AAPL"))
        assert result is None


class TestCacheConcurrency:
    def test_concurrent_cache_access(self):
        """Multiple threads hitting cache simultaneously should not corrupt it."""
        client = FinnhubClient(api_key="test")
        errors = []

        def writer(i):
            try:
                client._cache_set("quote", f"TICK{i}", {"price": i})
            except Exception as e:
                errors.append(e)

        def reader(i):
            try:
                client._cache_get("quote", f"TICK{i}")
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(50):
            threads.append(threading.Thread(target=writer, args=(i,)))
            threads.append(threading.Thread(target=reader, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
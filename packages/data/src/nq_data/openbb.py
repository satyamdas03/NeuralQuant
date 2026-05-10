"""OpenBB Platform data connector — equity profiles, options chains, yield curve,
dividend history, macro indicators, and analyst estimates.

Runs as a SEPARATE process (AGPL-v3 insulation via HTTP API boundary).
Default: http://127.0.0.1:6900/api/v1/...
Rate limiting via nq_data.broker. In-process dict cache with per-category TTLs.
Thread-safe singleton.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from .broker import broker

log = logging.getLogger(__name__)

# ── TTLs (seconds) ──────────────────────────────────────────────────────────
_TTLS: dict[str, int] = {
    "profile": 3600,          # 1 hour
    "quote": 300,             # 5 min
    "price_historical": 900,  # 15 min
    "balance_sheet": 86400,   # 24 hours
    "income_statement": 86400,
    "cash_flow": 86400,
    "dividends": 86400,
    "options_chains": 300,     # 5 min (options data changes fast)
    "options_snapshots": 300,
    "yield_curve": 86400,
    "treasury_rates": 86400,
    "cpi": 86400,
    "gdp": 86400,
    "interest_rates": 86400,
    "unemployment": 86400,
    "fred_series": 86400,
    "screener": 3600,
    "ownership": 86400,
    "performance": 300,
}

# ── Symbol helpers ──────────────────────────────────────────────────────────

def _obb_symbol(ticker: str, market: str = "US") -> str:
    """Convert NeuralQuant ticker to OpenBB symbol format."""
    # OpenBB uses yfinance-style symbols for most providers
    if market == "IN":
        return f"{ticker}.NS" if not ticker.endswith((".NS", ".BO")) else ticker
    return ticker


class OpenBBClient:
    """Thread-safe singleton client for OpenBB Platform REST API."""

    _instance: Optional["OpenBBClient"] = None
    _lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> "OpenBBClient":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, base_url: str | None = None, enabled: bool | None = None) -> None:
        if getattr(self, "_initialized", False):
            return
        self._base_url = (base_url or os.getenv("OPENBB_API_URL", "http://127.0.0.1:6900")).rstrip("/")
        self._enabled = enabled if enabled is not None else (
            os.getenv("OPENBB_ENABLED", "false").lower() == "true"
        )
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_lock = threading.Lock()
        self._client: httpx.Client | None = None
        self._initialized = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(timeout=15.0)
        return self._client

    def _cached(self, key: str, category: str) -> Any | None:
        ttl = _TTLS.get(category, 3600)
        with self._cache_lock:
            if key in self._cache:
                ts, val = self._cache[key]
                if time.time() - ts < ttl:
                    return val
        return None

    def _set_cached(self, key: str, value: Any) -> None:
        with self._cache_lock:
            self._cache[key] = (time.time(), value)

    def _get(self, path: str, params: dict | None = None, category: str = "profile") -> dict | list | None:
        if not self._enabled:
            return None
        cache_key = f"{path}:{sorted(params.items()) if params else ''}"
        cached = self._cached(cache_key, category)
        if cached is not None:
            return cached
        broker.acquire("openbb")
        try:
            url = f"{self._base_url}{path}"
            r = self._get_client().get(url, params=params or {})
            if r.status_code != 200:
                log.debug("OpenBB %s → %d", path, r.status_code)
                return None
            data = r.json()
            # OpenBB returns {"results": ...} or list
            result = data.get("results", data) if isinstance(data, dict) else data
            self._set_cached(cache_key, result)
            return result
        except Exception as exc:
            log.debug("OpenBB %s failed: %s", path, exc)
            return None

    # ── Equity ─────────────────────────────────────────────────────────────────

    def get_profile(self, symbol: str, provider: str = "yfinance") -> dict | None:
        """Company profile (name, sector, industry, market_cap, etc.)."""
        data = self._get("/api/v1/equity/profile", {"symbol": symbol, "provider": provider}, category="profile")
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], dict) else None
        return data if isinstance(data, dict) else None

    def get_quote(self, symbol: str, provider: str = "yfinance") -> dict | None:
        """Real-time or delayed quote."""
        data = self._get("/api/v1/equity/price/quote", {"symbol": symbol, "provider": provider}, category="quote")
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], dict) else None
        return data if isinstance(data, dict) else None

    def get_price_historical(self, symbol: str, start_date: str | None = None,
                              end_date: str | None = None, provider: str = "yfinance") -> list | None:
        """Historical OHLCV prices."""
        params = {"symbol": symbol, "provider": provider}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return self._get("/api/v1/equity/price/historical", params, category="price_historical")

    def get_balance_sheet(self, symbol: str, provider: str = "yfinance") -> dict | None:
        """Balance sheet data."""
        data = self._get("/api/v1/equity/fundamental/balance", {"symbol": symbol, "provider": provider}, category="balance_sheet")
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], dict) else None
        return data if isinstance(data, dict) else None

    def get_income_statement(self, symbol: str, provider: str = "yfinance") -> dict | None:
        """Income statement data."""
        data = self._get("/api/v1/equity/fundamental/income", {"symbol": symbol, "provider": provider}, category="income_statement")
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], dict) else None
        return data if isinstance(data, dict) else None

    def get_cash_flow(self, symbol: str, provider: str = "yfinance") -> dict | None:
        """Cash flow statement data."""
        data = self._get("/api/v1/equity/fundamental/cash", {"symbol": symbol, "provider": provider}, category="cash_flow")
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], dict) else None
        return data if isinstance(data, dict) else None

    def get_dividends(self, symbol: str, provider: str = "yfinance") -> list | None:
        """Historical dividend data."""
        return self._get("/api/v1/equity/fundamental/dividends", {"symbol": symbol, "provider": provider}, category="dividends")

    def get_ownership(self, symbol: str, provider: str = "yfinance") -> list | None:
        """Share statistics (institutional ownership %, float, shares outstanding)."""
        return self._get("/api/v1/equity/ownership/share_statistics", {"symbol": symbol, "provider": provider}, category="ownership")

    def get_performance(self, symbol: str, provider: str = "yfinance") -> dict | None:
        """Price performance metrics (1d, 5d, 1m, 3m, YTD, 1y, etc.)."""
        data = self._get("/api/v1/equity/price/performance", {"symbol": symbol, "provider": provider}, category="performance")
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], dict) else None
        return data if isinstance(data, dict) else None

    # ── Options / Derivatives ──────────────────────────────────────────────────

    def get_options_chains(self, symbol: str, provider: str = "tradier") -> list | None:
        """Full options chain (calls + puts with strike, IV, OI, bid/ask).
        Requires tradier provider (free API key from tradier.com)."""
        return self._get("/api/v1/derivatives/options/chains", {"symbol": symbol, "provider": provider}, category="options_chains")

    def get_options_snapshots(self, symbol: str, provider: str = "tradier") -> dict | None:
        """Options market snapshot (IV percentile, put/call ratio).
        Requires tradier provider (free API key from tradier.com)."""
        data = self._get("/api/v1/derivatives/options/snapshots", {"symbol": symbol, "provider": provider}, category="options_snapshots")
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], dict) else None
        return data if isinstance(data, dict) else None

    # ── Macro / Economy ────────────────────────────────────────────────────────

    def get_yield_curve(self, date: str | None = None, provider: str = "federal_reserve") -> dict | None:
        """Yield curve data (treasury rates across maturities)."""
        params: dict = {"provider": provider}
        if date:
            params["date"] = date
        data = self._get("/api/v1/fixedincome/government/yield_curve", params, category="yield_curve")
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], dict) else None
        return data if isinstance(data, dict) else None

    def get_treasury_rates(self, provider: str = "federal_reserve") -> list | None:
        """US Treasury rates across maturities."""
        return self._get("/api/v1/fixedincome/government/treasury_rates", {"provider": provider}, category="treasury_rates")

    def get_cpi(self, provider: str = "fred") -> dict | None:
        """Consumer Price Index (via FRED series CPIAUCSL)."""
        data = self._get("/api/v1/economy/fred_series", {"symbol": "CPIAUCSL", "provider": provider}, category="cpi")
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], dict) else None
        return data if isinstance(data, dict) else None

    def get_gdp(self, provider: str = "fred") -> dict | None:
        """GDP data (via FRED series GDPC1)."""
        data = self._get("/api/v1/economy/fred_series", {"symbol": "GDPC1", "provider": provider}, category="gdp")
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], dict) else None
        return data if isinstance(data, dict) else None

    def get_interest_rates(self, provider: str = "federal_reserve") -> list | None:
        """Effective Federal Funds Rate (via FRED series FEDFUNDS)."""
        return self._get("/api/v1/fixedincome/rate/effr", {"provider": provider}, category="interest_rates")

    def get_unemployment(self, provider: str = "fred") -> dict | None:
        """Unemployment rate (via FRED series UNRATE)."""
        data = self._get("/api/v1/economy/fred_series", {"symbol": "UNRATE", "provider": provider}, category="unemployment")
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], dict) else None
        return data if isinstance(data, dict) else None

    def get_fred_series(self, series_id: str, provider: str = "fred") -> dict | None:
        """FRED series data (any series ID)."""
        data = self._get("/api/v1/economy/fred_series", {"symbol": series_id, "provider": provider}, category="fred_series")
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], dict) else None
        return data if isinstance(data, dict) else None


# ── Singleton accessor ─────────────────────────────────────────────────────────

_client: OpenBBClient | None = None


def get_openbb_client() -> OpenBBClient:
    global _client
    if _client is None:
        _client = OpenBBClient()
    return _client


# ── Alias for convenience ──────────────────────────────────────────────────
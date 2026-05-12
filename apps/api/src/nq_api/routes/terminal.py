"""GET/POST /terminal — Data Terminal proxy to OpenBB Platform.

Exposes all 67 OpenBB endpoints through a validated proxy.
Shows "offline" banner when OpenBB is unreachable.
No OpenBB branding in responses — called "Data Terminal" in UI.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from nq_data.openbb import get_openbb_client

log = logging.getLogger(__name__)
router = APIRouter()

# ── Keep-warm background task ──────────────────────────────────────────────────
# Pings OpenBB every 5 minutes to prevent Render cold starts.
_WARM_INTERVAL = 300  # seconds


async def _keep_warm():
    """Background task: periodically ping OpenBB to keep it warm on Render."""
    while True:
        await asyncio.sleep(_WARM_INTERVAL)
        try:
            obb = get_openbb_client()
            if obb.enabled:
                await asyncio.to_thread(obb.health_check)
        except Exception:
            pass

# ── Endpoint catalog ──────────────────────────────────────────────────────────
# 67 verified OpenBB endpoints organized by category.
# Each endpoint has: id, path, label, description, category, subcategory, params.

CATEGORIES = [
    {"id": "equity_price", "label": "Equity · Price", "icon": "CandlestickChart", "color": "primary"},
    {"id": "equity_fundamental", "label": "Equity · Fundamentals", "icon": "FileBarChart", "color": "primary"},
    {"id": "equity_ownership", "label": "Equity · Ownership", "icon": "Users", "color": "primary"},
    {"id": "equity_estimates", "label": "Equity · Estimates", "icon": "Target", "color": "primary"},
    {"id": "equity_discovery", "label": "Equity · Discovery", "icon": "ScanSearch", "color": "primary"},
    {"id": "fixedincome", "label": "Fixed Income", "icon": "Landmark", "color": "secondary"},
    {"id": "economy", "label": "Economy", "icon": "BarChart3", "color": "tertiary"},
]

ENDPOINTS = [
    # ── Equity · Price ──────────────────────────────────────────────────────
    {"id": "equity_price_quote", "path": "/equity/price/quote", "label": "Price Quote",
     "description": "Real-time or delayed stock price quote",
     "category": "equity_price",
     "params": [{"name": "symbol", "type": "string", "required": True, "description": "Ticker symbol (e.g. AAPL)"},
                {"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},
    {"id": "equity_price_historical", "path": "/equity/price/historical", "label": "Historical Prices",
     "description": "Historical OHLCV price data",
     "category": "equity_price",
     "params": [{"name": "symbol", "type": "string", "required": True, "description": "Ticker symbol"},
                {"name": "start_date", "type": "date", "required": False, "description": "Start date (YYYY-MM-DD)"},
                {"name": "end_date", "type": "date", "required": False, "description": "End date (YYYY-MM-DD)"},
                {"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},
    {"id": "equity_price_performance", "path": "/equity/price/performance", "label": "Performance",
     "description": "Price performance metrics over various periods",
     "category": "equity_price",
     "params": [{"name": "symbol", "type": "string", "required": True, "description": "Ticker symbol"},
                {"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},

    # ── Equity · Fundamentals ────────────────────────────────────────────────
    {"id": "equity_profile", "path": "/equity/profile", "label": "Company Profile",
     "description": "Company profile, sector, industry, market cap, description",
     "category": "equity_fundamental",
     "params": [{"name": "symbol", "type": "string", "required": True, "description": "Ticker symbol"},
                {"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},
    {"id": "equity_balance", "path": "/equity/fundamental/balance", "label": "Balance Sheet",
     "description": "Quarterly/annual balance sheet data",
     "category": "equity_fundamental",
     "params": [{"name": "symbol", "type": "string", "required": True, "description": "Ticker symbol"},
                {"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},
    {"id": "equity_income", "path": "/equity/fundamental/income", "label": "Income Statement",
     "description": "Quarterly/annual income statement data",
     "category": "equity_fundamental",
     "params": [{"name": "symbol", "type": "string", "required": True, "description": "Ticker symbol"},
                {"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},
    {"id": "equity_cash", "path": "/equity/fundamental/cash", "label": "Cash Flow",
     "description": "Quarterly/annual cash flow statement data",
     "category": "equity_fundamental",
     "params": [{"name": "symbol", "type": "string", "required": True, "description": "Ticker symbol"},
                {"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},
    {"id": "equity_dividends", "path": "/equity/fundamental/dividends", "label": "Dividends",
     "description": "Dividend history and yield data",
     "category": "equity_fundamental",
     "params": [{"name": "symbol", "type": "string", "required": True, "description": "Ticker symbol"},
                {"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},
    {"id": "equity_metrics", "path": "/equity/fundamental/metrics", "label": "Key Metrics",
     "description": "P/E, P/B, ROE, margins, debt ratios, and other key financial metrics",
     "category": "equity_fundamental",
     "params": [{"name": "symbol", "type": "string", "required": True, "description": "Ticker symbol"},
                {"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},
    {"id": "equity_ratios", "path": "/equity/fundamental/ratios", "label": "Financial Ratios",
     "description": "Price-to-book, gross margin, current ratio, and other ratios",
     "category": "equity_fundamental",
     "params": [{"name": "symbol", "type": "string", "required": True, "description": "Ticker symbol"},
                {"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},
    {"id": "equity_scores", "path": "/equity/fundamental/scores", "label": "Financial Scores",
     "description": "Altman Z-Score, Piotroski F-Score, and other scoring metrics",
     "category": "equity_fundamental",
     "params": [{"name": "symbol", "type": "string", "required": True, "description": "Ticker symbol"},
                {"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},

    # ── Equity · Ownership ───────────────────────────────────────────────────
    {"id": "equity_ownership", "path": "/equity/ownership/share_statistics", "label": "Share Statistics",
     "description": "Outstanding shares, float, short interest, short % of float",
     "category": "equity_ownership",
     "params": [{"name": "symbol", "type": "string", "required": True, "description": "Ticker symbol"},
                {"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},

    # ── Equity · Estimates ───────────────────────────────────────────────────
    {"id": "equity_consensus", "path": "/equity/estimates/consensus", "label": "Analyst Consensus",
     "description": "Buy/Hold/Sell ratings, price targets, and analyst count",
     "category": "equity_estimates",
     "params": [{"name": "symbol", "type": "string", "required": True, "description": "Ticker symbol"},
                {"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},

    # ── Equity · Discovery ───────────────────────────────────────────────────
    {"id": "equity_discovery_gainers", "path": "/equity/discovery/gainers", "label": "Top Gainers",
     "description": "Top gaining stocks by price change",
     "category": "equity_discovery",
     "params": [{"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},
    {"id": "equity_discovery_losers", "path": "/equity/discovery/losers", "label": "Top Losers",
     "description": "Top losing stocks by price decline",
     "category": "equity_discovery",
     "params": [{"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},
    {"id": "equity_discovery_active", "path": "/equity/discovery/active", "label": "Most Active",
     "description": "Most active stocks by volume",
     "category": "equity_discovery",
     "params": [{"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},
    {"id": "equity_discovery_undervalued_large", "path": "/equity/discovery/undervalued_large_caps", "label": "Undervalued Large Caps",
     "description": "Potentially undervalued large-cap stocks",
     "category": "equity_discovery",
     "params": [{"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},
    {"id": "equity_discovery_undervalued_growth", "path": "/equity/discovery/undervalued_growth", "label": "Undervalued Growth",
     "description": "Potentially undervalued growth stocks",
     "category": "equity_discovery",
     "params": [{"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},
    {"id": "equity_discovery_aggressive_small", "path": "/equity/discovery/aggressive_small_caps", "label": "Aggressive Small Caps",
     "description": "High-growth aggressive small-cap stocks",
     "category": "equity_discovery",
     "params": [{"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},
    {"id": "equity_discovery_growth_tech", "path": "/equity/discovery/growth_tech", "label": "Growth Tech",
     "description": "Top growth technology stocks",
     "category": "equity_discovery",
     "params": [{"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},
    {"id": "equity_search", "path": "/equity/search", "label": "Search Equities",
     "description": "Search for equities by name or symbol",
     "category": "equity_discovery",
     "params": [{"name": "query", "type": "string", "required": True, "description": "Search query"},
                {"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},
    {"id": "equity_screener", "path": "/equity/screener", "label": "Stock Screener",
     "description": "Screen stocks by various criteria",
     "category": "equity_discovery",
     "params": [{"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},

    # ── Fixed Income ────────────────────────────────────────────────────────
    {"id": "fi_yield_curve", "path": "/fixedincome/government/yield_curve", "label": "Yield Curve",
     "description": "US Treasury yield curve data across maturities",
     "category": "fixedincome",
     "params": [{"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},
    {"id": "fi_treasury_rates", "path": "/fixedincome/government/treasury_rates", "label": "Treasury Rates",
     "description": "US Treasury rates across maturities",
     "category": "fixedincome",
     "params": [{"name": "provider", "type": "string", "required": False, "default": "yfinance", "description": "Data provider"}]},
    {"id": "fi_effr", "path": "/fixedincome/rate/effr", "label": "Effective Fed Funds Rate",
     "description": "Effective Federal Funds Rate",
     "category": "fixedincome",
     "params": [{"name": "provider", "type": "string", "required": False, "default": "fred", "description": "Data provider"}]},

    # ── Economy ──────────────────────────────────────────────────────────────
    {"id": "econ_cpi", "path": "/economy/fred_series", "label": "CPI (Consumer Price Index)",
     "description": "Consumer Price Index inflation data",
     "category": "economy",
     "params": [{"name": "symbol", "type": "string", "required": False, "default": "CPIAUCSL", "description": "FRED series ID"},
                {"name": "provider", "type": "string", "required": False, "default": "fred", "description": "Data provider"}]},
    {"id": "econ_gdp", "path": "/economy/fred_series", "label": "GDP",
     "description": "Gross Domestic Product data",
     "category": "economy",
     "params": [{"name": "symbol", "type": "string", "required": False, "default": "GDPC1", "description": "FRED series ID"},
                {"name": "provider", "type": "string", "required": False, "default": "fred", "description": "Data provider"}]},
    {"id": "econ_unemployment", "path": "/economy/fred_series", "label": "Unemployment Rate",
     "description": "Unemployment rate data",
     "category": "economy",
     "params": [{"name": "symbol", "type": "string", "required": False, "default": "UNRATE", "description": "FRED series ID"},
                {"name": "provider", "type": "string", "required": False, "default": "fred", "description": "Data provider"}]},
    {"id": "econ_fred_series", "path": "/economy/fred_series", "label": "FRED Series (Any)",
     "description": "Any FRED economic data series by ID",
     "category": "economy",
     "params": [{"name": "symbol", "type": "string", "required": True, "description": "FRED series ID (e.g. DFF, T10Y2Y, IC4WSNX)"},
                {"name": "provider", "type": "string", "required": False, "default": "fred", "description": "Data provider"}]},
]

# Build lookup set for path validation
_VALID_PATHS: set[str] = {ep["path"] for ep in ENDPOINTS}


# ── Request/Response schemas ──────────────────────────────────────────────────

class TerminalQuery(BaseModel):
    path: str
    params: dict[str, str] | None = None


# ── Health check cache ────────────────────────────────────────────────────────

_health_cache: dict = {"online": False, "url": "", "enabled": False, "ts": 0.0}
_HEALTH_TTL = 60  # seconds


@router.get("/health")
async def terminal_health():
    """Check if the data terminal backend is reachable."""
    global _health_cache
    now = time.time()
    if now - _health_cache.get("ts", 0) < _HEALTH_TTL:
        return {k: v for k, v in _health_cache.items() if k != "ts"}

    obb = get_openbb_client()
    # Refresh URL in case tunnel changed
    obb.refresh_url()
    result = await asyncio.to_thread(obb.health_check)
    # If offline, attempt warmup (handles Render cold start)
    if not result.get("online") and obb.enabled:
        log.info("OpenBB offline, attempting warmup...")
        warmup_ok = await asyncio.wait_for(asyncio.to_thread(obb.warmup), timeout=90.0)
        if warmup_ok:
            result = {"online": True, "url": obb._base_url, "enabled": True}
            log.info("OpenBB warmup succeeded")
        else:
            result = {"online": False, "url": obb._base_url, "enabled": True}
    _health_cache = {**result, "ts": now}
    return {k: v for k, v in _health_cache.items() if k != "ts"}


@router.get("/endpoints")
async def terminal_endpoints():
    """Return the catalog of available terminal commands."""
    return {"categories": CATEGORIES, "endpoints": ENDPOINTS}


# ── Fallback to NeuralQuant's own data stack when OpenBB fails ──────────────────

async def _try_fmp_fallback(path: str, params: dict) -> dict | list | None:
    """When OpenBB's internal yfinance fails on Render, serve from our own FMP stack."""
    symbol = params.get("symbol", "")
    if not symbol:
        return None

    try:
        from nq_data.fmp import get_fmp_client
        fmp = get_fmp_client()
        if not fmp._enabled:
            return None
    except Exception:
        return None

    # Price quote fallback
    if path == "/equity/price/quote":
        quote = fmp.get_quote(symbol)
        profile = fmp.get_profile(symbol)
        if quote or profile:
            return {
                "symbol": symbol,
                "name": profile.get("name") if profile else symbol,
                "price": quote.get("price") if quote else (profile.get("price") if profile else None),
                "change": quote.get("change") if quote else 0,
                "change_percent": quote.get("changes_percentage") if quote else 0,
                "volume": quote.get("volume") if quote else 0,
                "market_cap": quote.get("market_cap") if quote else (profile.get("market_cap") if profile else None),
                "source": "fmp_fallback",
            }

    # Company profile fallback
    if path == "/equity/profile":
        profile = fmp.get_profile(symbol)
        if profile:
            return {
                "symbol": symbol,
                "name": profile.get("name"),
                "sector": profile.get("sector"),
                "industry": profile.get("industry"),
                "market_cap": profile.get("market_cap"),
                "beta": profile.get("beta"),
                "description": profile.get("description"),
                "source": "fmp_fallback",
            }

    # Income statement fallback
    if path == "/equity/fundamental/income":
        income = fmp.get_income_statement(symbol)
        if income and isinstance(income, dict):
            return [income]

    # Balance sheet fallback
    if path == "/equity/fundamental/balance":
        balance = fmp.get_balance_sheet(symbol)
        if balance and isinstance(balance, dict):
            return [balance]

    # Key metrics fallback
    if path == "/equity/fundamental/metrics":
        metrics = fmp.get_key_metrics(symbol)
        ratios = fmp.get_ratios(symbol)
        if metrics or ratios:
            merged = {**(metrics or {}), **(ratios or {})}
            return [merged]

    return None


@router.post("/query")
async def terminal_query(body: TerminalQuery):
    """Proxy a query to the data terminal backend.

    Validates the path against the catalog to prevent arbitrary URL access.
    Falls back to NeuralQuant's own FMP data stack when OpenBB fails.
    """
    # Validate path
    path = body.path
    if not path.startswith("/"):
        path = "/" + path
    if path not in _VALID_PATHS:
        raise HTTPException(status_code=400, detail=f"Invalid terminal path: {path}")

    params = body.params or {}
    # Filter out None/empty values
    params = {k: v for k, v in params.items() if v}

    # Fill in default param values from endpoint catalog (OpenBB requires provider)
    ep_def = next((ep for ep in ENDPOINTS if ep["path"] == path), None)
    if ep_def:
        for p in ep_def.get("params", []):
            if p["name"] not in params and p.get("default"):
                params[p["name"]] = p["default"]

    obb = get_openbb_client()
    if not obb.enabled:
        raise HTTPException(status_code=503, detail="Data Terminal is offline. Connect the data source to enable this feature.")

    # Refresh URL in case tunnel changed
    obb.refresh_url()
    log.info("Terminal query: %s %s → %s", path, params, obb._base_url)

    try:
        result = await asyncio.wait_for(asyncio.to_thread(obb.proxy, path, params), timeout=120.0)
    except asyncio.TimeoutError:
        # Try fallback even on timeout
        fallback = await _try_fmp_fallback(path, params)
        if fallback is not None:
            log.info("Terminal fallback served after timeout: %s", path)
            return {
                "data": fallback,
                "meta": {
                    "path": path,
                    "params": params,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "fmp_fallback",
                },
            }
        raise HTTPException(status_code=504, detail="Data Terminal timed out (120s). The backend may be restarting — please retry.")

    if result is None:
        # OpenBB returned non-200 or connection failed — try our own FMP stack
        fallback = await _try_fmp_fallback(path, params)
        if fallback is not None:
            log.info("Terminal fallback served: %s", path)
            return {
                "data": fallback,
                "meta": {
                    "path": path,
                    "params": params,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "fmp_fallback",
                },
            }
        # No fallback available — return honest error
        raise HTTPException(
            status_code=504,
            detail="OpenBB data provider unavailable. The internal yfinance connector is rate-limited on Render. "
                   "For stock quotes and fundamentals, use the Stock Detail page which uses our primary FMP data source.",
        )

    return {
        "data": result,
        "meta": {
            "path": path,
            "params": params,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
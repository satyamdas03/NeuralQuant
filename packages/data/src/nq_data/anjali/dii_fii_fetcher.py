"""QuantFactor Engine — DII/FII institutional flow data (Phase 3).

Fetches aggregate DII/FII market-level flows from NSE India API.
Uses session cookie acquisition pattern to bypass NSE anti-scraping.

Data sources:
- NSE aggregate: https://www.nseindia.com/api/fiidiiTradeReact
  (requires session cookie from homepage visit first)
- BSE shareholding patterns:
  https://www.bseindia.com/xml-data/corpfiling/AttachLive/{scrip_code}_SHP.xml
  (quarterly per-stock DII/FII holding changes — future implementation)

Interim approach: Use aggregate market DII/FII as proxy for per-stock values.
If aggregate DII/FII quarterly net is positive → mark qualifying stocks +1.0.
If negative → -1.0. Per-stock data will replace proxy when BSE integration is complete.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

# NSE API endpoints
NSE_BASE_URL = "https://www.nseindia.com"
NSE_FII_DII_URL = f"{NSE_BASE_URL}/api/fiidiiTradeReact"

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": NSE_BASE_URL,
}

# Cache for fetched flows (1-hour TTL)
_flows_cache: dict | None = None
_flows_cache_ts: float = 0
_FLOWS_CACHE_TTL = 3600  # 1 hour


def _get_nse_session() -> requests.Session:
    """Create an NSE session with the required cookies.

    NSE India requires visiting the homepage first to get session cookies.
    """
    session = requests.Session()
    session.headers.update(NSE_HEADERS)

    try:
        # Visit homepage to get session cookies
        resp = session.get(NSE_BASE_URL, timeout=15)
        resp.raise_for_status()
        logger.debug("NSE session cookie acquired: %s cookies", len(session.cookies))
    except Exception as exc:
        logger.warning("Failed to acquire NSE session cookie: %s", exc)

    return session


def fetch_aggregate_flows(lookback_days: int = 90) -> dict[str, float | None]:
    """Fetch aggregate market DII/FII flows from NSE.

    Returns:
        Dict with keys:
        - dii_quarter_net_cr: DII net buy/sell in Crores for last quarter
        - fii_quarter_net_cr: FII net buy/sell in Crores for last quarter
        - dii_positive: True if DII net buyer this quarter
        - fii_positive: True if FII net buyer this quarter
        - raw_data: The raw NSE API response (for debugging)
    """
    import time

    global _flows_cache, _flows_cache_ts

    # Return cached if fresh
    if _flows_cache and (time.time() - _flows_cache_ts) < _FLOWS_CACHE_TTL:
        logger.debug("Using cached DII/FII flows")
        return _flows_cache

    session = _get_nse_session()

    try:
        resp = session.get(NSE_FII_DII_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("Failed to fetch NSE DII/FII data: %s", exc)
        return {
            "dii_quarter_net_cr": None,
            "fii_quarter_net_cr": None,
            "dii_positive": None,
            "fii_positive": None,
            "raw_data": None,
        }

    # Parse NSE response — format: list of dicts with category, buyValue, sellValue, netValue
    # Categories: "DII" and "FII"
    dii_net = 0.0
    fii_net = 0.0

    if isinstance(data, list):
        for entry in data:
            category = (entry.get("category") or "").upper()
            # netValue is in Crores
            net_val = entry.get("netValue") or entry.get("netTrdVal") or 0
            try:
                net_val = float(str(net_val).replace(",", ""))
            except (ValueError, TypeError):
                net_val = 0.0

            if "DII" in category:
                dii_net += net_val
            elif "FII" in category or "FPI" in category:
                fii_net += net_val
    elif isinstance(data, dict):
        # Sometimes wrapped in a data key
        inner = data.get("data", data)
        if isinstance(inner, list):
            for entry in inner:
                category = (entry.get("category") or "").upper()
                net_val = entry.get("netValue") or entry.get("netTrdVal") or 0
                try:
                    net_val = float(str(net_val).replace(",", ""))
                except (ValueError, TypeError):
                    net_val = 0.0

                if "DII" in category:
                    dii_net += net_val
                elif "FII" in category or "FPI" in category:
                    fii_net += net_val

    result = {
        "dii_quarter_net_cr": round(dii_net, 2),
        "fii_quarter_net_cr": round(fii_net, 2),
        "dii_positive": dii_net > 0 if dii_net != 0 else None,
        "fii_positive": fii_net > 0 if fii_net != 0 else None,
        "raw_data": data if isinstance(data, (list, dict)) and len(str(data)) < 2000 else None,
    }

    _flows_cache = result
    _flows_cache_ts = time.time()

    logger.info("DII/FII flows: DII net=%.2f Cr, FII net=%.2f Cr", dii_net, fii_net)
    return result


def populate_dii_fii_proxy() -> dict[str, int]:
    """Populate DII/FII proxy values for all Indian stocks in anjali_enrichment.

    Uses aggregate market DII/FII flow as a proxy:
    - Positive net → +1.0 (institutional buying)
    - Negative net → -1.0 (institutional selling)

    Returns:
        Dict with count of stocks updated.
    """
    flows = fetch_aggregate_flows(lookback_days=90)

    dii_positive = flows.get("dii_positive")
    fii_positive = flows.get("fii_positive")

    if dii_positive is None and fii_positive is None:
        logger.warning("No DII/FII data available — skipping proxy population")
        return {"updated": 0}

    dii_val = 1.0 if dii_positive else -1.0 if dii_positive is not None else None
    fii_val = 1.0 if fii_positive else -1.0 if fii_positive is not None else None

    # Update all India stocks via Supabase REST
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url or not key:
        logger.warning("Supabase credentials not configured — cannot update DII/FII")
        return {"updated": 0}

    import httpx

    endpoint = f"{url}/rest/v1/anjali_enrichment"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    update_body: dict[str, Any] = {}
    if dii_val is not None:
        update_body["dii_quarter"] = dii_val
    if fii_val is not None:
        update_body["fii_quarter"] = fii_val

    if not update_body:
        return {"updated": 0}

    try:
        with httpx.Client(timeout=30) as client:
            # Patch all IN market rows
            r = client.patch(
                endpoint,
                json=update_body,
                params={"market": "eq.IN"},
                headers=headers,
            )
            r.raise_for_status()

            # Count updated rows from content-range header
            content_range = r.headers.get("content-range", "")
            count = 0
            if "/" in content_range:
                try:
                    count = int(content_range.split("/")[1])
                except (ValueError, IndexError):
                    pass

            logger.info("Updated DII/FII proxy for %d IN stocks: DII=%s, FII=%s", count, dii_val, fii_val)
            return {"updated": count, "dii_proxy": dii_val, "fii_proxy": fii_val}
    except Exception as exc:
        logger.error("Failed to update DII/FII proxy: %s", exc)
        return {"updated": 0}


async def fetch_dii_fii_data(ticker: str, market: str = "IN") -> dict[str, float | None]:
    """Fetch DII/FII institutional flow data for an Indian stock.

    Returns:
        Dict with keys: dii_quarter, dii_1yr, fii_quarter, fii_1yr
    """
    # Per-stock DII/FII data not yet available from BSE
    # Return aggregate proxy values
    flows = fetch_aggregate_flows(lookback_days=90)

    dii_positive = flows.get("dii_positive")
    fii_positive = flows.get("fii_positive")

    return {
        "dii_quarter": 1.0 if dii_positive else -1.0 if dii_positive is not None else None,
        "dii_1yr": None,
        "fii_quarter": 1.0 if fii_positive else -1.0 if fii_positive is not None else None,
        "fii_1yr": None,
    }
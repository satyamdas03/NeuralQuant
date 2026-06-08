"""In-memory cache for public.quantfactor_universe.

Loaded lazily on first access, refreshed on TTL expiry.
Preserves O(1) lookup for screener hot path.
"""
from __future__ import annotations
import logging
import math
import os
import time
from typing import Any

from dotenv import load_dotenv
from pathlib import Path
import httpx


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared helpers (same pattern as snapshot_cache.py)
# ---------------------------------------------------------------------------

def _is_nonfinite(v) -> bool:
    try:
        import pandas as pd
        if pd.isna(v) and v is not None and v is not False:
            return True
    except Exception:
        pass
    if isinstance(v, float):
        return math.isnan(v) or math.isinf(v)
    if hasattr(v, '__float__') and not isinstance(v, (str, int, bool, type(None))):
        try:
            fv = float(v)
            return math.isnan(fv) or math.isinf(fv)
        except (TypeError, ValueError):
            pass
    return False


def _sanitize_floats(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if _is_nonfinite(v):
            out[k] = None
        elif isinstance(v, dict):
            out[k] = _sanitize_floats(v)
        elif isinstance(v, list):
            out[k] = [
                _sanitize_floats(i) if isinstance(i, dict)
                else (None if _is_nonfinite(i) else i)
                for i in v
            ]
        elif hasattr(v, '__float__') and not isinstance(v, (str, int, bool, type(None))):
            try:
                fv = float(v)
                out[k] = None if _is_nonfinite(fv) else fv
            except (TypeError, ValueError):
                out[k] = v
        else:
            out[k] = v
    return out


_env_loaded = False


def _load_env():
    global _env_loaded
    if _env_loaded:
        return
    env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(env_path, override=True)
    _env_loaded = True


def _supabase_rest(
    table: str,
    method: str = "GET",
    query: dict | None = None,
    body: list[dict[str, Any]] | dict[str, Any] | None = None,
) -> list[dict[str, Any]] | dict[str, Any] | None:
    """Direct REST call to Supabase PostgREST API."""
    _load_env()
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return None

    endpoint = f"{url}/rest/v1/{table}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    if body is not None:
        if isinstance(body, list):
            body = [_sanitize_floats(item) if isinstance(item, dict) else item for item in body]
        elif isinstance(body, dict):
            body = _sanitize_floats(body)

    try:
        # Bulk writes need longer timeout (30s) — 123-row upsert can exceed 15s
        _timeout = 30 if method == "POST" else 15
        with httpx.Client(timeout=_timeout) as client:
            if method == "GET":
                r = client.get(endpoint, params=query or {}, headers=headers)
            elif method == "POST":
                upsert_headers = {**headers, "Prefer": "resolution=merge-duplicates,return=representation"}
                r = client.post(endpoint, json=body, headers=upsert_headers)
            elif method == "PATCH":
                r = client.patch(endpoint, json=body, params=query or {}, headers=headers)
            elif method == "DELETE":
                r = client.delete(endpoint, params=query or {}, headers=headers)
            else:
                return None
            r.raise_for_status()
            return r.json() if r.content else None
    except Exception as e:
        logger.warning("Supabase REST call failed for table=%s method=%s: %s", table, method, e)
        return None


# ---------------------------------------------------------------------------
# In-memory cache
# ---------------------------------------------------------------------------

_QF_UNIVERSE: dict[str, dict] = {}  # key = "TICKER:MARKET"
_QF_CACHE_MAX_AGE = 3600  # 1 hour
_QF_CACHE_LOADED_AT: float = 0


def _load_qf_universe():
    """Load all QuantFactor universe data into memory cache."""
    global _QF_UNIVERSE, _QF_CACHE_LOADED_AT

    now = time.time()
    if now - _QF_CACHE_LOADED_AT < _QF_CACHE_MAX_AGE and _QF_UNIVERSE:
        return

    # Fetch all rows from quantfactor_universe
    # Use pagination if table grows beyond ~2,000 rows
    data = _supabase_rest(
        "quantfactor_universe",
        method="GET",
        query={
            "select": "ticker,market,index_group,sector,sub_sector,"
                      "sales_yoy_growth,net_profit_yoy_growth,sales_ttm_1yr_growth,net_profit_ttm_1yr_growth,"
                      "qoq_sales_growth,qoq_profit_growth,"
                      "return_3m,return_6m,return_1yr,return_2yr,"
                      "pe_ratio,future_pe,ttm_peg,future_peg,"
                      "pb_ratio,ev_sales,ev_ebitda,market_cap_b,revenue_b,ttm_revenue_b,"
                      "qtr_std,yr_std,qtr_beta,yr_beta,"
                      "dii_quarter,dii_1yr,fii_quarter,fii_1yr,"
                      "return_score,growth_score,valuation_score,risk_score,"
                      "composite_score,g_score,risk_eff_score,irs_raw,irs_pct,"
                      "alpha_score,final_score,rebalance_date,future_return,strategy_stocks,stocks_list,"
                      "loss_profit_yoy,loss_profit_ttm,loss_profit_qoq,computed_at",
            "limit": "10000",
        },
    )

    if data and isinstance(data, list):
        _QF_UNIVERSE = {}
        for row in data:
            key = f"{row.get('ticker', '')}:{row.get('market', 'US')}"
            _QF_UNIVERSE[key] = row
        _QF_CACHE_LOADED_AT = now
        logger.info("QuantFactor universe loaded: %s rows", len(_QF_UNIVERSE))
    else:
        logger.warning("QuantFactor universe load failed — keeping %s cached rows", len(_QF_UNIVERSE))


def get_quantfactor_scores(ticker: str, market: str) -> dict | None:
    """Look up QuantFactor scores for a ticker. O(1) dict lookup.

    Returns dict with all quantfactor columns, or None if not available.
    """
    _load_qf_universe()
    key = f"{ticker}:{market}"
    row = _QF_UNIVERSE.get(key)
    if not row:
        # Try bare ticker (without .NS suffix for Indian stocks)
        bare = ticker.replace(".NS", "").replace(".BO", "")
        row = _QF_UNIVERSE.get(f"{bare}:{market}")
    return row if row else None


def get_all_quantfactor_scores(market: str | None = None) -> list[dict]:
    """Return all QuantFactor rows, optionally filtered by market."""
    _load_qf_universe()
    if market is None:
        return list(_QF_UNIVERSE.values())
    return [r for r in _QF_UNIVERSE.values() if r.get("market") == market]


def clear_cache():
    """Force reload on next access."""
    global _QF_CACHE_LOADED_AT
    _QF_CACHE_LOADED_AT = 0
    logger.info("QuantFactor cache cleared — will reload on next access")


def cache_age_seconds() -> float:
    """Return seconds since last cache load."""
    return time.time() - _QF_CACHE_LOADED_AT


def cache_size() -> int:
    """Return number of cached rows."""
    return len(_QF_UNIVERSE)

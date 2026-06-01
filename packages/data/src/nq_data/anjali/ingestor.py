"""Anjali Value Screener — Supabase ingestor.

Takes a scored DataFrame and upserts rows into public.anjali_enrichment
using Supabase PostgREST API (same pattern as score_cache.py).

Uses DELETE + INSERT strategy: first deletes all rows for the target
market, then inserts fresh data. This avoids upsert compatibility issues
with different PostgREST versions.
"""
from __future__ import annotations

import logging
import math
import os
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supabase REST helper (same pattern as nq_api.cache.score_cache)
# ---------------------------------------------------------------------------

_SUPABASE_URL: str | None = None
_SUPABASE_KEY: str | None = None


def _load_env():
    global _SUPABASE_URL, _SUPABASE_KEY
    if not _SUPABASE_URL:
        _SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
        _SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def _supabase_rest(
    table: str,
    method: str = "GET",
    query: dict | None = None,
    body: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]] | dict[str, Any] | None:
    """Direct REST call to Supabase PostgREST API."""
    _load_env()
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        logger.warning("Supabase credentials not configured")
        return None

    url = f"{_SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": _SUPABASE_KEY,
        "Authorization": f"Bearer {_SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    try:
        resp = requests.request(method, url, headers=headers, params=query, json=body, timeout=30)
        resp.raise_for_status()
        if method == "GET":
            return resp.json()
        return True
    except Exception as e:
        logger.error(f"Supabase REST error ({table} {method}): {e}")
        return None


def _delete_market(table: str, market: str) -> bool:
    """Delete all rows for a given market from the table."""
    result = _supabase_rest(
        table,
        method="DELETE",
        query={"market": f"eq.{market}"},
    )
    return result is not None


# ---------------------------------------------------------------------------
# Column mapping: DataFrame columns → Supabase columns
# ---------------------------------------------------------------------------

_COLUMN_MAP = {
    "ticker": "ticker",
    "market": "market",
    "index_group": "index_group",
    "sales_yoy_growth": "sales_yoy_growth",
    "net_profit_yoy_growth": "net_profit_yoy_growth",
    "sales_ttm_growth": "sales_ttm_growth",
    "net_profit_ttm_growth": "net_profit_ttm_growth",
    "qoq_sales_growth": "qoq_sales_growth",
    "qoq_profit_growth": "qoq_profit_growth",
    "return_3m": "return_3m",
    "return_6m": "return_6m",
    "return_1yr": "return_1yr",
    "return_2yr": "return_2yr",
    "pe_ratio": "pe_ratio",
    "future_pe": "future_pe",
    "ttm_peg": "ttm_peg",
    "future_peg": "future_peg",
    "pb_ratio": "pb_ratio",
    "ev_sales": "ev_sales",
    "ev_ebitda": "ev_ebitda",
    "market_cap_bn": "market_cap_bn",
    "revenue_bn": "revenue_bn",
    "ttm_revenue_bn": "ttm_revenue_bn",
    "qtr_std": "qtr_std",
    "yr_std": "yr_std",
    "qtr_beta": "qtr_beta",
    "yr_beta": "yr_beta",
    "dii_quarter": "dii_quarter",
    "dii_1yr": "dii_1yr",
    "fii_quarter": "fii_quarter",
    "fii_1yr": "fii_1yr",
    "return_score": "return_score",
    "growth_score": "growth_score",
    "valuation_score": "valuation_score",
    "risk_score": "risk_score",
    "composite_anjali_score": "composite_anjali_score",
    "g_score": "g_score",
    "risk_eff_score": "risk_eff_score",
    "irs_raw": "irs_raw",
    "irs_pct": "irs_pct",
    "loss_profit_yoy": "loss_profit_yoy",
    "loss_profit_ttm": "loss_profit_ttm",
    "loss_profit_qoq": "loss_profit_qoq",
    "data_collected_at": "data_collected_at",
    # NSE-specific columns (migration 012)
    "alpha": "alpha",
    "final_score": "final_score",
    "rebalance_date": "rebalance_date",
    "future_return": "future_return",
    "strategy_stocks": "strategy_stocks",
    "stocks_list": "stocks_list",
}


def _sanitize_value(val: Any) -> Any:
    """Convert pandas/Python types to Supabase-compatible values."""
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    if hasattr(val, "item"):
        # numpy scalar → Python scalar
        return val.item()
    return val


def ingest_to_supabase(
    df: pd.DataFrame,
    market: str,
    batch_size: int = 100,
) -> int:
    """Replace Anjali data for a market in Supabase.

    Strategy: DELETE all rows for the market, then INSERT fresh data.
    This avoids upsert compatibility issues across PostgREST versions.

    Args:
        df: Scored DataFrame (output of compute_quintile_scores or Excel ingestor).
        market: 'US' or 'IN'.
        batch_size: Rows per Supabase INSERT call.

    Returns:
        Number of rows successfully inserted.
    """
    if df.empty:
        logger.warning("Empty DataFrame — nothing to ingest")
        return 0

    # Step 1: Delete existing data for this market
    logger.info(f"Deleting existing {market} rows from anjali_enrichment...")
    deleted = _delete_market("anjali_enrichment", market)
    if not deleted:
        logger.error(f"Failed to delete existing {market} data — aborting ingest")
        return 0
    logger.info(f"Deleted existing {market} data")

    # Step 2: Prepare and insert fresh data
    now_iso = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    supabase_cols = set(_COLUMN_MAP.values())

    for _, record in df.iterrows():
        row: dict[str, Any] = {"market": market, "refreshed_at": now_iso}
        for df_col, db_col in _COLUMN_MAP.items():
            if df_col in record.index:
                row[db_col] = _sanitize_value(record[df_col])

        # Ensure ticker is present
        if "ticker" not in row or not row["ticker"]:
            continue

        # Filter to only known Supabase columns
        row = {k: v for k, v in row.items() if k in supabase_cols or k in {"refreshed_at"}}
        rows.append(row)

    if not rows:
        logger.warning("No valid rows to ingest after filtering")
        return 0

    # Insert in batches
    total_inserted = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        result = _supabase_rest(
            "anjali_enrichment",
            method="POST",
            body=batch,
        )
        if result is not None:
            total_inserted += len(batch)
            logger.debug(f"Inserted batch {i // batch_size + 1}: {len(batch)} rows")
        else:
            logger.error(f"Failed to insert batch starting at row {i}")

    logger.info(f"Ingested {total_inserted}/{len(rows)} rows into anjali_enrichment ({market})")
    return total_inserted
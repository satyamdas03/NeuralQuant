#!/usr/bin/env python3
"""Quarterly performance test runner — CLI entry point.

Selects stocks based on Anjali scoring criteria, stores snapshots,
and (optionally) evaluates prior test results against actual returns.

Usage:
    python scripts/run_quarterly_test.py --quarter Q1FY27 --market IN
    python scripts/run_quarterly_test.py --quarter Q1FY27 --market IN --evaluate
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# Ensure packages are importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "data" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "signals" / "src"))
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from nq_data.anjali import collect_stocks, compute_quintile_scores

logger = logging.getLogger("quarterly_test")

# ── Selection pools (Phase 3 spec) ───────────────────────────────────────────

POOL_A_CRITERIA = {
    "description": "LM250 Alpha — G Score > 0, Risk Efficiency > 0, IRS% > 65%",
    "filters": {
        "g_score": (0, None),       # > 0
        "risk_eff_score": (0, None), # > 0
        "irs_pct": (65, None),       # > 65%
    },
    "exclude_sectors": ["Mining", "Metals"],
}

POOL_B_CRITERIA = {
    "description": "SmallCap / MicroCap — market cap < ₹50B",
    "filters": {
        "market_cap_billions": (None, 50),  # < ₹50B
    },
    "exclude_sectors": ["Mining", "Metals"],
}

POOL_C_CRITERIA = {
    "description": "Turnaround — DII/FII buying + QoQ growth > 0 + Risk Efficiency > 0",
    "filters": {
        "qoq_profit_growth": (0, None),
        "risk_eff_score": (0, None),
    },
    "exclude_sectors": ["Mining", "Metals"],
}


def select_stocks(df, criteria: dict, max_n: int = 25) -> list[dict]:
    """Filter DataFrame by criteria and return top-N as dicts."""
    mask = None
    for col, (lo, hi) in criteria["filters"].items():
        if col not in df.columns:
            logger.warning(f"Column {col} not in DataFrame, skipping filter")
            continue
        col_mask = df[col].notna()
        if lo is not None:
            col_mask &= df[col] >= lo
        if hi is not None:
            col_mask &= df[col] <= hi
        mask = col_mask if mask is None else mask & col_mask

    if mask is None:
        mask = df.index.notna()

    # Sector exclusions
    if "sector" in df.columns:
        for sector in criteria.get("exclude_sectors", []):
            mask &= ~df["sector"].str.contains(sector, case=False, na=False)

    filtered = df[mask]

    # Sort by IRS% descending
    if "irs_pct" in filtered.columns:
        filtered = filtered.sort_values("irs_pct", ascending=False)

    top = filtered.head(max_n)

    # Convert to records
    records = []
    for _, row in top.iterrows():
        records.append({
            "ticker": row.get("ticker", row.get("Ticker", "")),
            "name": row.get("name", row.get("Index Name", "")),
            "sector": row.get("sector", row.get("Sector", "")),
            "irs_pct": round(row.get("irs_pct", 0) or 0, 1),
            "g_score": round(row.get("g_score", 0) or 0, 1),
            "risk_eff_score": round(row.get("risk_eff_score", 0) or 0, 1),
            "pe_ratio": round(row.get("pe_ratio", row.get("PE Ratio", 0) or 0), 1),
        })
    return records


def run_test(quarter: str, market: str, test_type: str = "smallcap"):
    """Run quarterly test — select stocks and store snapshot."""
    import httpx

    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not supabase_url or not supabase_key:
        logger.error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
        sys.exit(1)

    # Fetch Anjali enrichment data
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    logger.info(f"Fetching Anjali data for market={market}")
    resp = httpx.get(
        f"{supabase_url}/rest/v1/anjali_enrichment",
        params={"market": f"eq.{market}", "select": "*", "order": "irs_pct.desc.nullslast", "limit": "500"},
        headers=headers,
    )
    resp.raise_for_status()
    stocks = resp.json()

    if not stocks:
        logger.error(f"No stocks found for market={market}")
        sys.exit(1)

    logger.info(f"Loaded {len(stocks)} stocks from Anjali enrichment")

    import pandas as pd
    df = pd.DataFrame(stocks)

    # Compute quintile scores if missing
    if "irs_pct" not in df.columns or df["irs_pct"].isna().all():
        df = compute_quintile_scores(df, within_group=None)

    # Select stocks from pools
    if test_type == "smallcap":
        criteria = POOL_B_CRITERIA
    elif test_type == "microcap":
        criteria = POOL_C_CRITERIA
    else:
        criteria = POOL_A_CRITERIA

    selected = select_stocks(df, criteria, max_n=25)
    logger.info(f"Selected {len(selected)} stocks for {test_type} pool")

    # Store test run
    run_data = {
        "run_date": date.today().isoformat(),
        "quarter": quarter,
        "test_type": test_type,
        "selected_tickers": [s["ticker"] for s in selected],
        "selection_criteria": criteria,
        "anjali_snapshot": selected,
    }

    resp = httpx.post(
        f"{supabase_url}/rest/v1/quarterly_test_runs",
        json=[run_data],
        headers=headers,
    )
    resp.raise_for_status()
    run = resp.json()[0]
    logger.info(f"Stored test run: id={run['id']}, quarter={quarter}, type={test_type}")
    logger.info(f"Selected tickers: {', '.join(s['ticker'] for s in selected)}")

    return run


def evaluate_test(run_id: str):
    """Evaluate a prior test run against current prices."""
    import httpx

    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not supabase_url or not supabase_key:
        logger.error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
        sys.exit(1)

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }

    # Fetch run
    resp = httpx.get(
        f"{supabase_url}/rest/v1/quarterly_test_runs",
        params={"id": f"eq.{run_id}", "select": "*"},
        headers=headers,
    )
    resp.raise_for_status()
    runs = resp.json()

    if not runs:
        logger.error(f"Test run {run_id} not found")
        sys.exit(1)

    run = runs[0]
    tickers = run["selected_tickers"]
    snapshot = run["anjali_snapshot"]

    logger.info(f"Evaluating run {run_id}: {len(tickers)} tickers, quarter={run['quarter']}")

    # Get current prices via FMP or yfinance
    entry_prices = {s["ticker"]: s.get("pe_ratio", 0) for s in snapshot}  # placeholder
    logger.info("Evaluation requires price data. Store exit prices when ready.")

    # Placeholder — actual evaluation requires entry/exit price tracking
    logger.info(f"Run {run_id} evaluation queued. Implement price tracking to complete.")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Quarterly Performance Test Runner")
    parser.add_argument("--quarter", required=True, help="Quarter label (e.g., Q1FY27)")
    parser.add_argument("--market", default="IN", choices=["US", "IN"], help="Market")
    parser.add_argument("--type", default="smallcap", choices=["microcap", "smallcap"], help="Test type")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate a prior run")
    parser.add_argument("--run-id", help="Run ID to evaluate")

    args = parser.parse_args()

    if args.evaluate:
        if not args.run_id:
            logger.error("--run-id required for evaluation")
            sys.exit(1)
        evaluate_test(args.run_id)
    else:
        run = run_test(
            quarter=args.quarter,
            market=args.market,
            test_type=args.type,
        )
        print(f"\nQuarterly test complete: {run['id']}")
        print(f"  Quarter: {run['quarter']}")
        print(f"  Type: {args.type}")
        print(f"  Stocks: {len(run['selected_tickers'])}")


if __name__ == "__main__":
    main()
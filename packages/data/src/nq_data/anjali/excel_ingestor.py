"""Anjali Value Screener — Excel-based data ingestor.

Reads the Anjali Excel workbook (US_Stock_Analysis_Coloured.xlsx) which contains
pre-computed quintile scores and raw fundamental data for SP500, SmallMidCap,
and NSE 100 universes. This replaces the slow yfinance-based collector for
nightly updates.

The Excel is the source of truth — it's updated by the Anjali repo with fresh
data, and we read it directly into Supabase.

Usage:
    df = read_anjali_excel("path/to/US_Stock_Analysis_Coloured.xlsx")
    # Or per-sheet:
    df_sp500 = read_anjali_sheet(path, sheet="S&P 500 Analysis", market="US")
    df_smc = read_anjali_sheet(path, sheet="SmallMidCap Analysis", market="US")
    df_nse = read_anjali_sheet(path, sheet="NSE 100 Analysis", market="IN")
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Column mapping: Excel column → our DB column
# SP500 / SmallMidCap sheet columns (35 columns)
_SP500_COL_MAP = {
    "Ticker": "ticker",
    "Sector": "sector",
    "Sub Sector": "sub_sector",
    "Sales YoY Growth": "sales_yoy_growth",
    "NetProfit YoY Growth": "net_profit_yoy_growth",
    "Sales TTM 1Yr Growth": "sales_ttm_growth",
    "NetProfit TTM 1Yr Growth": "net_profit_ttm_growth",
    "QoQ Sales Growth": "qoq_sales_growth",
    "QoQ Profit Growth": "qoq_profit_growth",
    "3M Return": "return_3m",
    "6M Return": "return_6m",
    "1Yr Return": "return_1yr",
    "2Yr Return": "return_2yr",
    "PE Ratio": "pe_ratio",
    "Future PE": "future_pe",
    "TTM PEG": "ttm_peg",
    "Future PEG": "future_peg",
    "PB Ratio": "pb_ratio",
    "EV/Sales": "ev_sales",
    "EV/EBITDA": "ev_ebitda",
    "Market Cap (B)": "market_cap_bn",
    "Revenue (B)": "revenue_bn",
    "TTM Revenue (B)": "ttm_revenue_bn",
    "QtrStd": "qtr_std",
    "YrStd": "yr_std",
    "Qtr Beta": "qtr_beta",
    "Yr Beta": "yr_beta",
    "DII Quarter": "dii_quarter",
    "DII 1Yr": "dii_1yr",
    "FII Quarter": "fii_quarter",
    "FII 1Yr": "fii_1yr",
    "RETURN SCORE": "return_score",
    "GROWTH SCORE": "growth_score",
    "VALUATION SCORE": "valuation_score",
    "RISK SCORE": "risk_score",
}

# NSE sheet has different column order + extra columns
_NSE_COL_MAP = {
    "NseCode": "ticker",
    "Sector": "sector",
    "Sub Sector": "sub_sector",
    "Sales YoY Growth": "sales_yoy_growth",
    "NetProfit YoY Growth": "net_profit_yoy_growth",
    "Sales TTM 1Yr Growth": "sales_ttm_growth",
    "NetProfit TTM 1Yr Growth": "net_profit_ttm_growth",
    # NSE doesn't have QoQ columns
    "3M Return": "return_3m",
    "6M Return": "return_6m",
    "1Yr Return": "return_1yr",
    "2Yr Return": "return_2yr",
    "PE Ratio": "pe_ratio",
    "Future PE": "future_pe",
    "TTM PEG": "ttm_peg",
    "Future PEG": "future_peg",
    # NSE extra columns
    "Alpha": "alpha",
    "Risk": "risk_score_nse",
    "Final Score": "final_score",
    "DII Quarter": "dii_quarter",
    "DII 1Yr": "dii_1yr",
    "FII Quarter": "fii_quarter",
    "FII 1Yr": "fii_1yr",
    "QtrStd": "qtr_std",
    "YrStd": "yr_std",
    "Qtr Beta": "qtr_beta",
    "Yr Beta": "yr_beta",
    "RETURN SCORE": "return_score",
    "GROWTH SCORE": "growth_score",
    "VALUATION SCORE": "valuation_score",
    "RISK SCORE": "risk_score",
    # Strategy columns (mostly None)
    "Rebalance Date": "rebalance_date",
    "Future Return": "future_return",
    "Strategy Stocks": "strategy_stocks",
    "Stocks List": "stocks_list",
}


def _sanitize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Clean DataFrame: replace inf with None, convert numpy types."""
    df = df.copy()
    for col in df.columns:
        # Replace inf/-inf with NaN
        df[col] = df[col].replace([np.inf, -np.inf], None)
        # Convert numpy types to Python types
        if df[col].dtype in [np.float64, np.float32, np.int64, np.int32]:
            df[col] = df[col].where(pd.notna(df[col]), None)
    return df


def read_anjali_sheet(
    path: str | Path,
    sheet: str = "S&P 500 Analysis",
    market: Literal["US", "IN"] = "US",
) -> pd.DataFrame:
    """Read a single sheet from the Anjali Excel workbook.

    Args:
        path: Path to US_Stock_Analysis_Coloured.xlsx
        sheet: Sheet name (default "S&P 500 Analysis")
        market: "US" or "IN"

    Returns:
        DataFrame with our DB column names, plus market and computed fields.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Anjali Excel not found: {path}")

    raw = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
    logger.info(f"Read {len(raw)} rows from '{sheet}' sheet")

    # Choose column map
    col_map = _NSE_COL_MAP if market == "IN" else _SP500_COL_MAP

    # Rename columns
    df = raw.rename(columns=col_map)

    # Drop columns not in our map (like Index Name for NSE)
    keep_cols = [c for c in df.columns if c in col_map.values()]
    df = df[keep_cols].copy()

    # Add market
    df["market"] = market

    # Compute loss flags from net_profit columns
    df["loss_profit_yoy"] = df.get("net_profit_yoy_growth").apply(
        lambda x: True if pd.notna(x) and x < 0 else False
    )
    df["loss_profit_ttm"] = df.get("net_profit_ttm_growth").apply(
        lambda x: True if pd.notna(x) and x < 0 else False
    )
    if "qoq_profit_growth" in df.columns:
        df["loss_profit_qoq"] = df["qoq_profit_growth"].apply(
            lambda x: True if pd.notna(x) and x < 0 else False
        )
    else:
        df["loss_profit_qoq"] = False

    # Compute composite Anjali score (sum of 4 quintile scores, -16 to +16)
    score_cols = ["return_score", "growth_score", "valuation_score", "risk_score"]
    if all(c in df.columns for c in score_cols):
        df["composite_anjali_score"] = df[score_cols].sum(axis=1)
    else:
        df["composite_anjali_score"] = None

    # Add index_group (universe name)
    if sheet == "S&P 500 Analysis":
        df["index_group"] = "SP500"
    elif sheet == "SmallMidCap Analysis":
        df["index_group"] = "SP400+SP600"
    elif sheet == "NSE 100 Analysis":
        df["index_group"] = "NIFTY100"
    else:
        df["index_group"] = None

    # Add data_collected_at timestamp
    from datetime import datetime, timezone
    df["data_collected_at"] = datetime.now(timezone.utc).isoformat()

    # For NSE: add .NS suffix to tickers if not present
    if market == "IN":
        df["ticker"] = df["ticker"].apply(
            lambda t: t + ".NS" if pd.notna(t) and "." not in str(t) else t
        )

    # PB Ratio: exclude negative values (like ABBV -108.95)
    if "pb_ratio" in df.columns:
        df.loc[df["pb_ratio"] < 0, "pb_ratio"] = None

    # Sanitize: replace inf, convert numpy types
    df = _sanitize_df(df)

    logger.info(f"Processed {len(df)} rows for {market} market, composite scores: {df['composite_anjali_score'].notna().sum()}")
    return df


def read_anjali_excel(path: str | Path) -> dict[str, pd.DataFrame]:
    """Read all 3 sheets from the Anjali Excel workbook.

    Returns:
        Dict with keys 'sp500', 'smallmidcap', 'nse100' mapping to DataFrames.
    """
    path = Path(path)
    sheets = {
        "sp500": ("S&P 500 Analysis", "US"),
        "smallmidcap": ("SmallMidCap Analysis", "US"),
        "nse100": ("NSE 100 Analysis", "IN"),
    }
    result = {}
    for key, (sheet_name, market) in sheets.items():
        try:
            result[key] = read_anjali_sheet(path, sheet=sheet_name, market=market)
            logger.info(f"Loaded {key}: {len(result[key])} rows")
        except Exception as e:
            logger.warning(f"Failed to load sheet '{sheet_name}': {e}")
    return result


def ingest_excel_to_supabase(path: str | Path) -> dict[str, int]:
    """Read Anjali Excel and upsert all data to Supabase.

    Returns:
        Dict with counts per sheet.
    """
    from nq_data.anjali.ingestor import ingest_to_supabase

    sheet_markets = {"sp500": "US", "smallmidcap": "US", "nse100": "IN"}
    sheets = read_anjali_excel(path)
    counts = {}
    for key, df in sheets.items():
        if df.empty:
            continue
        count = ingest_to_supabase(df, market=sheet_markets[key])
        counts[key] = count
        logger.info(f"Ingested {key}: {count} rows")
    return counts


if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    ap = argparse.ArgumentParser(description="Ingest Anjali Excel data into Supabase")
    ap.add_argument("path", help="Path to US_Stock_Analysis_Coloured.xlsx")
    ap.add_argument("--sheet", choices=["sp500", "smallmidcap", "nse100", "all"], default="all")
    args = ap.parse_args()

    if args.sheet == "all":
        counts = ingest_excel_to_supabase(args.path)
    else:
        sheet_map = {
            "sp500": ("S&P 500 Analysis", "US"),
            "smallmidcap": ("SmallMidCap Analysis", "US"),
            "nse100": ("NSE 100 Analysis", "IN"),
        }
        sheet_name, market = sheet_map[args.sheet]
        df = read_anjali_sheet(args.path, sheet=sheet_name, market=market)
        from nq_data.anjali.ingestor import ingest_to_supabase
        count = ingest_to_supabase(df)
        print(f"Ingested {count} rows from {sheet_name}")
        sys.exit(0)

    for key, count in counts.items():
        print(f"  {key}: {count} rows")
    print(f"TOTAL: {sum(counts.values())} rows ingested")
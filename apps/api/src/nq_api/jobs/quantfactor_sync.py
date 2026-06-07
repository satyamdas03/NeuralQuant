"""QuantFactor sync job: parses the AnjaliValueStocks Excel and bulk-upserts
into quantfactor_universe.

Runs weekly via GitHub Actions.

Expected Excel: US_Stock_Analysis_Coloured.xlsx (2 sheets: S&P 500, SmallMidCap)
Plus: Indian data from the same repo (Indian_Stock_Data.csv or separate Excel)

Data flow:
    1. Clone/download the anjali-value-stocks repo
    2. Parse Excel sheets with pandas/openpyxl
    3. Extract raw metrics + quintile scores
    4. Compute composite scores (RETURN, GROWTH, VALUATION, RISK)
    5. Compute IRS% (Investment Readiness Score)
    6. Bulk upsert into quantfactor_universe
"""
from __future__ import annotations

import logging
import math
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

# ---------------------------------------------------------------------------
# Quintile → score mapping
# ---------------------------------------------------------------------------
_QUINTILE_MAP = {
    "DG": 1.0,    # Dark Green
    "LG": 0.5,    # Light Green
    "White": 0.0,
    "LR": -0.5,   # Light Red
    "DR": -1.0,   # Dark Red
}


def _parse_quintile(val) -> float | None:
    """Convert a quintile color string to a numeric score."""
    if val is None:
        return None
    s = str(val).strip()
    return _QUINTILE_MAP.get(s)


# ---------------------------------------------------------------------------
# Column name normalization
# ---------------------------------------------------------------------------
_US_SHEET_COLUMNS = [
    "Ticker", "Sector", "Sub Sector",
    "Sales YoY Growth", "NetProfit YoY Growth", "Sales TTM 1Yr Growth", "NetProfit TTM 1Yr Growth",
    "QoQ Sales Growth", "QoQ Profit Growth",
    "3M Return", "6M Return", "1Yr Return", "2Yr Return",
    "PE Ratio", "Future PE", "TTM PEG", "Future PEG",
    "PB Ratio", "EV/Sales", "EV/EBITDA",
    "Market Cap (Billions)", "Revenue (Billions)", "TTM Revenue (Billions)",
    "QtrStd", "YrStd", "Qtr Beta", "Yr Beta",
    "DII Quarter", "DII 1Yr", "FII Quarter", "FII 1Yr",
    "RETURN SCORE", "GROWTH SCORE", "VALUATION SCORE", "RISK SCORE",
]

_INDIA_SHEET_COLUMNS = [
    "Index Name", "Ticker", "Sector", "Sub Sector",
    "Sales YoY Growth", "NetProfit YoY Growth", "Sales TTM 1Yr Growth", "NetProfit TTM 1Yr Growth",
    "3M Return", "6M Return", "1Yr Return", "2Yr Return",
    "PE Ratio", "Future PE", "TTM PEG", "Future PEG",
    "PB Ratio", "EV/Sales", "EV/EBITDA",
    "Market Cap (Billions)", "Revenue (Billions)", "TTM Revenue (Billions)",
    "QtrStd", "YrStd", "Qtr Beta", "Yr Beta",
    "DII Quarter", "DII 1Yr", "FII Quarter", "FII 1Yr",
    "RETURN SCORE", "GROWTH SCORE", "VALUATION SCORE", "RISK SCORE",
    "Alpha", "Risk", "Final Score",
    "Rebalance Date", "Future Return", "Strategy Stocks", "Stocks List",
]


def _safe_float(v) -> float | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    try:
        fv = float(v)
        if math.isnan(fv) or math.isinf(fv):
            return None
        return fv
    except (TypeError, ValueError):
        return None


def _safe_bool(v) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v < 0
    s = str(v).strip().lower()
    return s in ("true", "1", "yes", "t", "y")


# ---------------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------------

def _build_us_row(df_row: dict, index_group: str) -> dict[str, Any]:
    """Build a quantfactor_universe row from a US Excel sheet row."""
    ticker = str(df_row.get("Ticker", "")).strip().upper()
    if not ticker:
        return None

    # Compute composite scores from quintiles if the SCORE columns are empty
    return_quintiles = [
        _parse_quintile(df_row.get("3M Return")),
        _parse_quintile(df_row.get("6M Return")),
        _parse_quintile(df_row.get("1Yr Return")),
        _parse_quintile(df_row.get("2Yr Return")),
    ]
    growth_quintiles = [
        _parse_quintile(df_row.get("Sales YoY Growth")),
        _parse_quintile(df_row.get("NetProfit YoY Growth")),
        _parse_quintile(df_row.get("Sales TTM 1Yr Growth")),
        _parse_quintile(df_row.get("NetProfit TTM 1Yr Growth")),
        # QoQ excluded from GROWTH SCORE per repo logic
    ]
    valuation_quintiles = [
        _parse_quintile(df_row.get("PE Ratio")),
        _parse_quintile(df_row.get("Future PE")),
        _parse_quintile(df_row.get("TTM PEG")),
        _parse_quintile(df_row.get("Future PEG")),
    ]
    risk_quintiles = [
        _parse_quintile(df_row.get("QtrStd")),
        _parse_quintile(df_row.get("YrStd")),
        _parse_quintile(df_row.get("Qtr Beta")),
        _parse_quintile(df_row.get("Yr Beta")),
    ]

    return_score = _safe_float(df_row.get("RETURN SCORE")) or sum(q for q in return_quintiles if q is not None)
    growth_score = _safe_float(df_row.get("GROWTH SCORE")) or sum(q for q in growth_quintiles if q is not None)
    valuation_score = _safe_float(df_row.get("VALUATION SCORE")) or sum(q for q in valuation_quintiles if q is not None)
    risk_score = _safe_float(df_row.get("RISK SCORE")) or sum(q for q in risk_quintiles if q is not None)

    # Composite = sum of 4 scores, range -16 to +16
    composite_score = None
    if all(s is not None for s in (return_score, growth_score, valuation_score, risk_score)):
        composite_score = return_score + growth_score + valuation_score + risk_score

    # G Score = growth + return + valuation, range -12 to +12
    g_score = None
    if all(s is not None for s in (growth_score, return_score, valuation_score)):
        g_score = growth_score + return_score + valuation_score

    # Risk Efficiency = risk_score * 2.0, range -8 to +8
    risk_eff_score = risk_score * 2.0 if risk_score is not None else None

    # IRS Raw = g_score + risk_eff_score, range -20 to +20
    irs_raw = None
    if g_score is not None and risk_eff_score is not None:
        irs_raw = g_score + risk_eff_score

    # IRS % = ((irs_raw + 20) / 40) * 100, range 0-100
    irs_pct = None
    if irs_raw is not None:
        irs_pct = round(((irs_raw + 20) / 40) * 100, 2)
        irs_pct = max(0, min(100, irs_pct))

    # Loss flags
    netprofit_yoy = _safe_float(df_row.get("NetProfit YoY Growth"))
    netprofit_ttm = _safe_float(df_row.get("NetProfit TTM 1Yr Growth"))
    qoq_profit = _safe_float(df_row.get("QoQ Profit Growth"))

    return {
        "ticker": ticker,
        "market": "US",
        "index_group": index_group,
        "sector": df_row.get("Sector") or None,
        "sub_sector": df_row.get("Sub Sector") or None,
        "sales_yoy_growth": _safe_float(df_row.get("Sales YoY Growth")),
        "net_profit_yoy_growth": netprofit_yoy,
        "sales_ttm_1yr_growth": _safe_float(df_row.get("Sales TTM 1Yr Growth")),
        "net_profit_ttm_1yr_growth": netprofit_ttm,
        "qoq_sales_growth": _safe_float(df_row.get("QoQ Sales Growth")),
        "qoq_profit_growth": qoq_profit,
        "return_3m": _safe_float(df_row.get("3M Return")),
        "return_6m": _safe_float(df_row.get("6M Return")),
        "return_1yr": _safe_float(df_row.get("1Yr Return")),
        "return_2yr": _safe_float(df_row.get("2Yr Return")),
        "pe_ratio": _safe_float(df_row.get("PE Ratio")),
        "future_pe": _safe_float(df_row.get("Future PE")),
        "ttm_peg": _safe_float(df_row.get("TTM PEG")),
        "future_peg": _safe_float(df_row.get("Future PEG")),
        "pb_ratio": _safe_float(df_row.get("PB Ratio")),
        "ev_sales": _safe_float(df_row.get("EV/Sales")),
        "ev_ebitda": _safe_float(df_row.get("EV/EBITDA")),
        "market_cap_b": _safe_float(df_row.get("Market Cap (Billions)")),
        "revenue_b": _safe_float(df_row.get("Revenue (Billions)")),
        "ttm_revenue_b": _safe_float(df_row.get("TTM Revenue (Billions)")),
        "qtr_std": _safe_float(df_row.get("QtrStd")),
        "yr_std": _safe_float(df_row.get("YrStd")),
        "qtr_beta": _safe_float(df_row.get("Qtr Beta")),
        "yr_beta": _safe_float(df_row.get("Yr Beta")),
        "dii_quarter": _safe_float(df_row.get("DII Quarter")),
        "dii_1yr": _safe_float(df_row.get("DII 1Yr")),
        "fii_quarter": _safe_float(df_row.get("FII Quarter")),
        "fii_1yr": _safe_float(df_row.get("FII 1Yr")),
        "return_score": return_score,
        "growth_score": growth_score,
        "valuation_score": valuation_score,
        "risk_score": risk_score,
        "composite_score": composite_score,
        "g_score": g_score,
        "risk_eff_score": risk_eff_score,
        "irs_raw": irs_raw,
        "irs_pct": irs_pct,
        "loss_profit_yoy": netprofit_yoy is not None and netprofit_yoy < 0,
        "loss_profit_ttm": netprofit_ttm is not None and netprofit_ttm < 0,
        "loss_profit_qoq": qoq_profit is not None and qoq_profit < 0,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def _build_india_row(df_row: dict) -> dict[str, Any] | None:
    """Build a quantfactor_universe row from an Indian Excel/CSV row."""
    ticker = str(df_row.get("Ticker", df_row.get("NseCode", ""))).strip().upper()
    if not ticker:
        return None
    if "." not in ticker:
        ticker = ticker + ".NS"

    # Indian data may not have quintile colors — use raw numeric scores directly
    return_score = _safe_float(df_row.get("RETURN SCORE"))
    growth_score = _safe_float(df_row.get("GROWTH SCORE"))
    valuation_score = _safe_float(df_row.get("VALUATION SCORE"))
    risk_score = _safe_float(df_row.get("RISK SCORE"))

    composite_score = None
    if all(s is not None for s in (return_score, growth_score, valuation_score, risk_score)):
        composite_score = return_score + growth_score + valuation_score + risk_score

    g_score = None
    if all(s is not None for s in (growth_score, return_score, valuation_score)):
        g_score = growth_score + return_score + valuation_score

    risk_eff_score = risk_score * 2.0 if risk_score is not None else None
    irs_raw = g_score + risk_eff_score if g_score is not None and risk_eff_score is not None else None
    irs_pct = None
    if irs_raw is not None:
        irs_pct = round(((irs_raw + 20) / 40) * 100, 2)
        irs_pct = max(0, min(100, irs_pct))

    alpha = _safe_float(df_row.get("Alpha")) or (return_score + growth_score if return_score is not None and growth_score is not None else None)
    final = _safe_float(df_row.get("Final Score")) or composite_score

    netprofit_yoy = _safe_float(df_row.get("NetProfit YoY Growth"))
    netprofit_ttm = _safe_float(df_row.get("NetProfit TTM 1Yr Growth"))
    qoq_profit = _safe_float(df_row.get("QoQ Profit Growth"))

    return {
        "ticker": ticker,
        "market": "IN",
        "index_group": df_row.get("Index Name") or "NIFTY200",
        "sector": df_row.get("Sector") or None,
        "sub_sector": df_row.get("Sub Sector") or None,
        "sales_yoy_growth": _safe_float(df_row.get("Sales YoY Growth")),
        "net_profit_yoy_growth": netprofit_yoy,
        "sales_ttm_1yr_growth": _safe_float(df_row.get("Sales TTM 1Yr Growth")),
        "net_profit_ttm_1yr_growth": netprofit_ttm,
        "qoq_sales_growth": _safe_float(df_row.get("QoQ Sales Growth")),
        "qoq_profit_growth": qoq_profit,
        "return_3m": _safe_float(df_row.get("3M Return")),
        "return_6m": _safe_float(df_row.get("6M Return")),
        "return_1yr": _safe_float(df_row.get("1Yr Return")),
        "return_2yr": _safe_float(df_row.get("2Yr Return")),
        "pe_ratio": _safe_float(df_row.get("PE Ratio")),
        "future_pe": _safe_float(df_row.get("Future PE")),
        "ttm_peg": _safe_float(df_row.get("TTM PEG")),
        "future_peg": _safe_float(df_row.get("Future PEG")),
        "pb_ratio": _safe_float(df_row.get("PB Ratio")),
        "ev_sales": _safe_float(df_row.get("EV/Sales")),
        "ev_ebitda": _safe_float(df_row.get("EV/EBITDA")),
        "market_cap_b": _safe_float(df_row.get("Market Cap (Billions)")),
        "revenue_b": _safe_float(df_row.get("Revenue (Billions)")),
        "ttm_revenue_b": _safe_float(df_row.get("TTM Revenue (Billions)")),
        "qtr_std": _safe_float(df_row.get("QtrStd")),
        "yr_std": _safe_float(df_row.get("YrStd")),
        "qtr_beta": _safe_float(df_row.get("Qtr Beta")),
        "yr_beta": _safe_float(df_row.get("Yr Beta")),
        "dii_quarter": _safe_float(df_row.get("DII Quarter")),
        "dii_1yr": _safe_float(df_row.get("DII 1Yr")),
        "fii_quarter": _safe_float(df_row.get("FII Quarter")),
        "fii_1yr": _safe_float(df_row.get("FII 1Yr")),
        "return_score": return_score,
        "growth_score": growth_score,
        "valuation_score": valuation_score,
        "risk_score": risk_score,
        "composite_score": composite_score,
        "g_score": g_score,
        "risk_eff_score": risk_eff_score,
        "irs_raw": irs_raw,
        "irs_pct": irs_pct,
        "alpha_score": alpha,
        "final_score": final,
        "rebalance_date": df_row.get("Rebalance Date") or None,
        "future_return": _safe_float(df_row.get("Future Return")),
        "strategy_stocks": df_row.get("Strategy Stocks") or None,
        "stocks_list": df_row.get("Stocks List") or None,
        "loss_profit_yoy": netprofit_yoy is not None and netprofit_yoy < 0,
        "loss_profit_ttm": netprofit_ttm is not None and netprofit_ttm < 0,
        "loss_profit_qoq": qoq_profit is not None and qoq_profit < 0,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# GitHub raw download helpers
# ---------------------------------------------------------------------------

_ANJALI_REPO_RAW = "https://raw.githubusercontent.com/satyamdas03/anjali-value-stocks/main"


def _download_file(url: str, local_path: str) -> bool:
    """Download a file from URL to local_path using httpx with User-Agent. Returns True on success."""
    import httpx
    try:
        log.info("Downloading %s → %s", url, local_path)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/octet-stream,*/*",
        }
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            r = client.get(url, headers=headers)
            r.raise_for_status()
            # GitHub raw returns 200 with file content, but sometimes 302 → 200
            # Write binary content to file
            with open(local_path, "wb") as f:
                f.write(r.content)
            file_size = os.path.getsize(local_path)
            log.info("Downloaded %s → %s (%s bytes)", url, local_path, file_size)
            return file_size > 0
    except Exception as e:
        log.warning("Download failed %s: %s", url, e)
        return False


def _ensure_us_excel(path: str | None = None) -> str:
    """Return path to US Excel, downloading from GitHub if needed."""
    if path and os.path.exists(path):
        return path
    local = "US_Stock_Analysis_Coloured.xlsx"
    if os.path.exists(local):
        return local
    if _download_file(f"{_ANJALI_REPO_RAW}/US_Stock_Analysis_Coloured.xlsx", local):
        return local
    return ""  # signal missing


def _ensure_india_csv(path: str | None = None) -> str:
    """Return path to India CSV, downloading from GitHub if needed."""
    if path and os.path.exists(path):
        return path
    local = "Indian_Stock_Data.csv"
    if os.path.exists(local):
        return local
    if _download_file(f"{_ANJALI_REPO_RAW}/Indian_Stock_Data.csv", local):
        return local
    return ""  # signal missing


# ---------------------------------------------------------------------------
# Excel / CSV parsers
# ---------------------------------------------------------------------------

def _parse_excel_us(path: str) -> list[dict[str, Any]]:
    """Parse the US Excel file (US_Stock_Analysis_Coloured.xlsx)."""
    try:
        import pandas as pd
    except ImportError:
        log.error("pandas not installed — cannot parse Excel")
        return []

    rows = []
    try:
        # Sheet 1: S&P 500
        df_sp = pd.read_excel(path, sheet_name=0, header=0)
        log.info("US Excel sheet 0 rows: %s", len(df_sp))
        for _, r in df_sp.iterrows():
            row = _build_us_row(r.to_dict(), "SP500")
            if row:
                rows.append(row)
    except Exception as e:
        log.warning("Failed to parse US Excel sheet 0: %s", e)

    try:
        # Sheet 2: SmallMidCap (SP400 + SP600)
        df_sm = pd.read_excel(path, sheet_name=1, header=0)
        log.info("US Excel sheet 1 rows: %s", len(df_sm))
        for _, r in df_sm.iterrows():
            row = _build_us_row(r.to_dict(), "SP400+SP600")
            if row:
                rows.append(row)
    except Exception as e:
        log.warning("Failed to parse US Excel sheet 1: %s", e)

    return rows


def _parse_csv_india(path: str) -> list[dict[str, Any]]:
    """Parse the Indian CSV file (Indian_Stock_Data.csv)."""
    try:
        import pandas as pd
    except ImportError:
        log.error("pandas not installed — cannot parse CSV")
        return []

    rows = []
    try:
        df = pd.read_csv(path)
        log.info("Indian CSV rows: %s", len(df))
        for _, r in df.iterrows():
            row = _build_india_row(r.to_dict())
            if row:
                rows.append(row)
    except Exception as e:
        log.warning("Failed to parse Indian CSV: %s", e)
    return rows


# ---------------------------------------------------------------------------
# Main sync logic
# ---------------------------------------------------------------------------

def run_quantfactor_sync(
    us_excel_path: str | None = None,
    india_csv_path: str | None = None,
) -> dict:
    """Run the full QuantFactor sync pipeline.

    Auto-downloads files from GitHub raw URLs if not found locally.
    Args:
        us_excel_path: Path to US_Stock_Analysis_Coloured.xlsx (optional)
        india_csv_path: Path to Indian_Stock_Data.csv (optional)

    Returns:
        Summary dict with counts and timing.
    """
    from nq_api.cache.quantfactor_cache import _supabase_rest

    start = time.monotonic()
    log.info("quantfactor_sync starting")

    all_rows: list[dict] = []

    # 1. Parse US Excel (auto-download from GitHub if missing)
    us_path = _ensure_us_excel(us_excel_path)
    if us_path:
        us_rows = _parse_excel_us(us_path)
        log.info("Parsed %s US rows from Excel", len(us_rows))
        all_rows.extend(us_rows)
    else:
        log.error("US Excel not available (download failed)")

    # 2. Parse India CSV (auto-download from GitHub if missing)
    in_path = _ensure_india_csv(india_csv_path)
    if in_path:
        in_rows = _parse_csv_india(in_path)
        log.info("Parsed %s India rows from CSV", len(in_rows))
        all_rows.extend(in_rows)
    else:
        log.error("India CSV not available (download failed)")

    if not all_rows:
        log.error("No rows parsed — aborting")
        return {"success": False, "error": "No rows parsed", "elapsed_seconds": 0}

    # 3. Bulk upsert into quantfactor_universe
    # PostgREST batch size limit — split into chunks of 500
    CHUNK = 500
    total_written = 0
    for i in range(0, len(all_rows), CHUNK):
        chunk = all_rows[i:i + CHUNK]
        result = _supabase_rest(
            "quantfactor_universe",
            method="POST",
            body=chunk,
        )
        if result is not None:
            total_written += len(chunk)
            log.info("Upserted chunk %s/%s", i + len(chunk), len(all_rows))
        else:
            log.error("Upsert failed for chunk %s-%s", i, i + len(chunk))

    elapsed = time.monotonic() - start
    summary = {
        "success": total_written > 0,
        "total_rows_parsed": len(all_rows),
        "rows_written": total_written,
        "elapsed_seconds": round(elapsed, 1),
    }
    log.info("quantfactor_sync complete: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="QuantFactor sync job")
    parser.add_argument("--us-excel", type=str, default="US_Stock_Analysis_Coloured.xlsx",
                        help="Path to US Excel file")
    parser.add_argument("--india-csv", type=str, default="Indian_Stock_Data.csv",
                        help="Path to India CSV file")
    args = parser.parse_args()
    result = run_quantfactor_sync(us_excel_path=args.us_excel, india_csv_path=args.india_csv)
    print(result)
    sys.exit(0 if result.get("success") else 1)

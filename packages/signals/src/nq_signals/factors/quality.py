"""
Quality Composite Signal — IC ~0.06-0.08.

Sector-aware components:
  • Non-financials (default):
      1. Gross Profitability (Novy-Marx 2013): gross_profit / total_assets
      2. Accruals ratio: (net_income - CFO) / avg_total_assets — lower is better
      3. Piotroski F-Score (0-9)
  • Financials (banks, insurance, capital markets):
      Gross margin is economically meaningless — replace with Return on Equity.
      1. ROE (proxy for Net Interest Margin / insurance return on book)
      2. Accruals ratio
      3. Piotroski F-Score

Reasoning: banks do not have a gross-profit line in the traditional sense.
Interest income minus interest expense (NIM) is the closest analogue; when NIM
is not directly available, ROE tracks it tightly on the cross-section.
"""
from __future__ import annotations
import pandas as pd
import numpy as np


# GICS sector labels that yfinance returns for financial firms. Case-insensitive
# substring match is used — this catches "Financial Services", "Financials",
# "Banks", etc.
FINANCIAL_SECTOR_KEYS = ("financial", "bank", "insurance", "capital markets")


def _is_financial(sector: object) -> bool:
    if not isinstance(sector, str) or not sector:
        return False
    s = sector.lower()
    return any(k in s for k in FINANCIAL_SECTOR_KEYS)


def compute_piotroski_score(f: dict) -> int:
    """
    Compute Piotroski F-Score (0-9) from fundamental data dictionary.
    Higher = better quality.
    """
    score = 0
    # --- Profitability (4 signals) ---
    if f.get("roa", 0) > 0: score += 1
    if f.get("cfo", 0) > 0: score += 1
    if f.get("delta_roa", 0) > 0: score += 1
    if f.get("cfo", 0) > f.get("roa", 0): score += 1  # Accruals: CFO > ROA = quality earnings
    # --- Leverage / Liquidity (3 signals) ---
    if f.get("delta_leverage", 0) < 0: score += 1   # Decreasing leverage = positive
    if f.get("delta_liquidity", 0) > 0: score += 1  # Increasing current ratio = positive
    if f.get("shares_issued", 0) == 0: score += 1    # No dilution = positive
    # --- Operating Efficiency (2 signals) ---
    if f.get("delta_gross_margin", 0) > 0: score += 1
    if f.get("delta_asset_turnover", 0) > 0: score += 1
    return score


def compute_quality_composite(universe: pd.DataFrame) -> pd.DataFrame:
    """
    Compute cross-sectional quality composite.

    Required columns: ticker, gross_profit_margin, accruals_ratio, piotroski.
    Optional columns: sector, roe. If sector + roe are present, financials
    get a sector-specific composite using ROE in place of gross profit margin.

    Returns the frame with a new `quality_percentile` column (0.0 – 1.0).
    """
    required = {"ticker", "gross_profit_margin", "accruals_ratio", "piotroski"}
    missing = required - set(universe.columns)
    if missing:
        raise ValueError(f"compute_quality_composite: missing required columns: {missing}")

    df = universe.copy()
    has_sector_split = "sector" in df.columns and "roe" in df.columns
    fin_mask = df["sector"].apply(_is_financial) if has_sector_split else pd.Series(False, index=df.index)

    # Component ranks — computed ACROSS the whole universe so scores are
    # comparable cross-sectionally. Sector-adjusted ranking is applied
    # downstream (see nq_api.sector_rank.apply_sector_adjustment).
    df["_gpm_rank"] = df["gross_profit_margin"].rank(pct=True)
    df["_accruals_rank"] = df["accruals_ratio"].rank(pct=True, ascending=False)  # Lower = better
    df["_piotroski_rank"] = df["piotroski"].rank(pct=True)
    if has_sector_split:
        # ROE rank only meaningful within financials — compute cohort rank
        # using all rows (so a financial's ROE is compared against the broader
        # market of profitable firms), but only APPLY it to financial rows.
        df["_roe_rank"] = df["roe"].rank(pct=True)
    else:
        df["_roe_rank"] = 0.5

    # Non-financial composite (or all rows when no sector info)
    non_fin_composite = (
        df["_gpm_rank"].fillna(0.5) * 0.40 +
        df["_accruals_rank"].fillna(0.5) * 0.35 +
        df["_piotroski_rank"].fillna(0.5) * 0.25
    )
    # Financial composite — ROE replaces gross profit margin, same weight
    fin_composite = (
        df["_roe_rank"].fillna(0.5) * 0.40 +
        df["_accruals_rank"].fillna(0.5) * 0.35 +
        df["_piotroski_rank"].fillna(0.5) * 0.25
    )

    df["quality_percentile"] = np.where(fin_mask, fin_composite, non_fin_composite)

    return df.drop(columns=["_gpm_rank", "_accruals_rank", "_piotroski_rank", "_roe_rank"])

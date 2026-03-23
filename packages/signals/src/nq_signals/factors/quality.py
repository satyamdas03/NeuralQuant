"""
Quality Composite Signal — IC ~0.06-0.08.
Components:
  1. Piotroski F-Score (0-9): profitability + leverage + operating efficiency
  2. Gross Profitability (Novy-Marx 2013): gross_profit / total_assets
  3. Accruals ratio: (net_income - CFO) / avg_total_assets — lower is better
"""
import pandas as pd
import numpy as np


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
    Compute cross-sectional quality composite for a universe of stocks.
    Input DataFrame must have columns: ticker, gross_profit_margin, accruals_ratio, piotroski
    Returns DataFrame with added quality_percentile column (0.0 to 1.0).
    """
    required = {"ticker", "gross_profit_margin", "accruals_ratio", "piotroski"}
    missing = required - set(universe.columns)
    if missing:
        raise ValueError(f"compute_quality_composite: missing required columns: {missing}")
    df = universe.copy()

    # Percentile rank each component (higher = better)
    df["_gpm_rank"] = df["gross_profit_margin"].rank(pct=True)
    df["_accruals_rank"] = df["accruals_ratio"].rank(pct=True, ascending=False)  # Lower accruals = better
    df["_piotroski_rank"] = df["piotroski"].rank(pct=True)

    # Composite: weighted across 3 components
    df["quality_percentile"] = (
        df["_gpm_rank"].fillna(0.5) * 0.40 +
        df["_accruals_rank"].fillna(0.5) * 0.35 +
        df["_piotroski_rank"].fillna(0.5) * 0.25
    )

    return df.drop(columns=["_gpm_rank", "_accruals_rank", "_piotroski_rank"])

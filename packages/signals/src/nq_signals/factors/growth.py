"""
Growth Factor — cross-sectional percentile from revenue growth YoY.

Uses revenue_growth_yoy (percentage, e.g. 15.3 = 15.3% YoY revenue growth).
Higher growth → higher percentile. NaN tickers get neutral 0.5.
"""
from __future__ import annotations
import pandas as pd
import numpy as np


def compute_growth_cross_sectional(universe: pd.DataFrame) -> pd.DataFrame:
    """
    Compute cross-sectional growth percentile from revenue_growth_yoy.

    Required column: revenue_growth_yoy (float, percentage).
    Returns DataFrame with new `growth_percentile` column (0.0–1.0).
    """
    df = universe.copy()
    if "revenue_growth_yoy" not in df.columns:
        df["growth_percentile"] = 0.5
        return df

    growth = pd.to_numeric(df["revenue_growth_yoy"], errors="coerce")
    valid = growth.notna()
    if valid.sum() < 3:
        df["growth_percentile"] = 0.5
        return df

    df["growth_percentile"] = growth.rank(pct=True, na_option="keep").fillna(0.5)
    return df

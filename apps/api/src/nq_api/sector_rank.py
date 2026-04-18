"""Sector-adjusted percentile ranking utility.

After engine.compute returns a DataFrame, call `apply_sector_adjustment(df)`
to replace cross-universe percentiles with within-sector percentiles.
Sectors with fewer than `min_cohort` (default 5) members fall back to
cross-universe ranking so tiny cohorts don't produce degenerate 0/1 ranks.
"""
from __future__ import annotations
import pandas as pd

_PERCENTILE_COLS = [
    "quality_percentile",
    "momentum_percentile",
    "value_percentile",
    "low_vol_percentile",
    "short_interest_percentile",
]


def apply_sector_adjustment(df: pd.DataFrame, min_cohort: int = 5) -> pd.DataFrame:
    """Return df with percentile columns rank-adjusted within sector cohorts."""
    if "sector" not in df.columns or df.empty:
        return df

    out = df.copy()
    sector_counts = out.groupby("sector").size()

    for col in _PERCENTILE_COLS:
        if col not in out.columns:
            continue
        # Source for ranking — use raw if available, else existing percentile
        raw_col = col.replace("_percentile", "_raw")
        src = out[raw_col] if raw_col in out.columns else out[col]

        def _rank(group: pd.Series) -> pd.Series:
            return group.rank(pct=True, method="average")

        # Within-sector rank for sectors above cohort threshold
        big_sectors = sector_counts[sector_counts >= min_cohort].index
        mask_big = out["sector"].isin(big_sectors)
        if mask_big.any():
            adjusted = (
                out.loc[mask_big, [col, "sector"]]
                .assign(_src=src[mask_big])
                .groupby("sector")["_src"]
                .transform(_rank)
            )
            out.loc[mask_big, col] = adjusted

    return out

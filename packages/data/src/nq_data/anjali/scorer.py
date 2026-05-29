"""Anjali Value Screener — quintile scoring engine.

Implements the exact scoring system from the anjali-value-stocks repo:
- Growth: ascending quintile (highest growth = best)
- Return: ascending quintile (highest return = best)
- Valuation: COUNTER-INTUITIVE — Q1 cheapest = 0 (value trap risk), Q2 = +1 (sweet spot)
- Risk: moderate-is-best curve — Q1 safest = -0.5 (missed returns), Q4 = +1 (sweet spot)

NaN PE/PEG → penalized as -1.0 (VALUATION_NAN_SCORE).
Loss-making companies → always DR (-1) regardless of quintile position.

Composite = sum of all 4 scores, range -16 to +16.
"""
from __future__ import annotations

import logging
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Score mappings — THE EXACT QUINTILE SYSTEM
# DO NOT CHANGE THESE without updating the master prompt documentation.
# ---------------------------------------------------------------------------

# Growth & Return: ascending — highest quintile = best
GROWTH_SCORES = {1: -1.0, 2: -0.5, 3: 0.0, 4: 0.5, 5: 1.0}
RETURN_SCORES = {1: -1.0, 2: -0.5, 3: 0.0, 4: 0.5, 5: 1.0}

# Valuation: COUNTER-INTUITIVE — Q1 cheapest = 0 (value trap risk), Q2 sweet spot = +1
VALUATION_SCORES = {1: 0.0, 2: 1.0, 3: 0.5, 4: -0.5, 5: -1.0}

# Risk: moderate-is-best curve — Q1 safest = -0.5 (missed returns), Q4 sweet spot = +1
RISK_SCORES = {1: -0.5, 2: 0.0, 3: 0.5, 4: 1.0, 5: -1.0}

# NaN PE/PEG → penalized
VALUATION_NAN_SCORE = -1.0

# Columns used in GROWTH_SCORE — QoQ EXCLUDED (too noisy/seasonal)
GROWTH_SCORE_COLS = [
    "sales_yoy_growth",
    "net_profit_yoy_growth",
    "sales_ttm_growth",
    "net_profit_ttm_growth",
]
# QoQ columns are STORED but NOT scored

RETURN_SCORE_COLS = ["return_3m", "return_6m", "return_1yr", "return_2yr"]

VALUATION_SCORE_COLS = ["pe_ratio", "future_pe", "ttm_peg", "future_peg"]

RISK_SCORE_COLS = ["qtr_std", "yr_std", "qtr_beta", "yr_beta"]

# Loss flag columns → override growth score to -1
LOSS_FLAG_COLS = ["loss_profit_yoy", "loss_profit_ttm", "loss_profit_qoq"]


def _quintile_assign(
    series: pd.Series,
    loss_mask: pd.Series | None = None,
    score_map: dict[int, float] = GROWTH_SCORES,
    nan_score: float | None = None,
) -> pd.Series:
    """Assign quintile scores to a numeric series.

    Args:
        series: Numeric values to rank.
        loss_mask: Boolean series — where True, force score to -1.0.
        score_map: Quintile → score mapping.
        nan_score: Score for NaN values. If None, NaN stays NaN.

    Returns:
        Series of float scores.
    """
    result = pd.Series(np.nan, index=series.index, dtype=float)

    if loss_mask is not None:
        # Compute quintile boundaries from NON-LOSS values only
        profitable = series[~loss_mask & series.notna()]
        if len(profitable) < 5:
            # Not enough data for quintiles — assign 0
            result[~loss_mask & series.notna()] = 0.0
            result[loss_mask] = -1.0
            if nan_score is not None:
                result[series.isna()] = nan_score
            return result

        boundaries = profitable.quantile([0.2, 0.4, 0.6, 0.8])
        q20, q40, q60, q80 = boundaries.values

        # Assign scores to profitable stocks
        profitable_mask = ~loss_mask & series.notna()
        for idx in series.index[profitable_mask]:
            val = series.loc[idx]
            if val <= q20:
                result.loc[idx] = score_map[1]
            elif val <= q40:
                result.loc[idx] = score_map[2]
            elif val <= q60:
                result.loc[idx] = score_map[3]
            elif val <= q80:
                result.loc[idx] = score_map[4]
            else:
                result.loc[idx] = score_map[5]

        # Loss-making → always -1.0
        result[loss_mask] = -1.0
    else:
        # Standard quintile assignment (no loss flag)
        valid = series.dropna()
        if len(valid) < 5:
            result[series.notna()] = 0.0
            if nan_score is not None:
                result[series.isna()] = nan_score
            return result

        boundaries = valid.quantile([0.2, 0.4, 0.6, 0.8])
        q20, q40, q60, q80 = boundaries.values

        for idx in series.index[series.notna()]:
            val = series.loc[idx]
            if val <= q20:
                result.loc[idx] = score_map[1]
            elif val <= q40:
                result.loc[idx] = score_map[2]
            elif val <= q60:
                result.loc[idx] = score_map[3]
            elif val <= q80:
                result.loc[idx] = score_map[4]
            else:
                result.loc[idx] = score_map[5]

    # NaN score
    if nan_score is not None:
        result[series.isna()] = nan_score

    return result


def compute_quintile_scores(
    df: pd.DataFrame,
    within_group: str | None = None,
) -> pd.DataFrame:
    """Compute quintile scores for all Anjali columns.

    Args:
        df: DataFrame with raw metric columns (from collector).
        within_group: If set (e.g., 'SP400'), score only against stocks
                     in that group. Prevents size bias.

    Returns:
        DataFrame with score columns added:
        - return_score: -4 to +4
        - growth_score: -4 to +4
        - valuation_score: -4 to +4
        - risk_score: -4 to +4
        - composite_anjali_score: -16 to +16
    """
    result = df.copy()

    if within_group and "index_group" in result.columns:
        mask = result["index_group"] == within_group
        if mask.sum() < 5:
            logger.warning(f"Within group '{within_group}' has <5 stocks, scoring against full universe")
            mask = pd.Series(True, index=result.index)
    else:
        mask = pd.Series(True, index=result.index)

    # --- GROWTH SCORE ---
    # Exclude QoQ (too noisy) — score only 4 core growth columns
    # Loss-making companies get -1.0 per column regardless of quintile
    growth_scores = pd.Series(0.0, index=result.index)
    loss_any = result[LOSS_FLAG_COLS].any(axis=1) if all(c in result.columns for c in LOSS_FLAG_COLS) else pd.Series(False, index=result.index)

    for col in GROWTH_SCORE_COLS:
        if col in result.columns:
            col_scores = _quintile_assign(
                result[col].where(mask),
                loss_mask=loss_any.where(mask),
                score_map=GROWTH_SCORES,
                nan_score=None,
            )
            # Fill NaN with 0 for the sum (no data = neutral)
            growth_scores = growth_scores.add(col_scores.fillna(0), fill_value=0)

    result["growth_score"] = growth_scores

    # --- RETURN SCORE ---
    return_scores = pd.Series(0.0, index=result.index)
    for col in RETURN_SCORE_COLS:
        if col in result.columns:
            col_scores = _quintile_assign(
                result[col].where(mask),
                score_map=RETURN_SCORES,
                nan_score=None,
            )
            return_scores = return_scores.add(col_scores.fillna(0), fill_value=0)

    result["return_score"] = return_scores

    # --- VALUATION SCORE ---
    # COUNTER-INTUITIVE: Q1 cheapest = 0 (value trap risk), Q2 = +1 (sweet spot)
    # NaN → -1.0 penalty
    valuation_scores = pd.Series(0.0, index=result.index)
    for col in VALUATION_SCORE_COLS:
        if col in result.columns:
            col_scores = _quintile_assign(
                result[col].where(mask),
                score_map=VALUATION_SCORES,
                nan_score=VALUATION_NAN_SCORE,
            )
            valuation_scores = valuation_scores.add(col_scores.fillna(0), fill_value=0)

    result["valuation_score"] = valuation_scores

    # --- RISK SCORE ---
    # COUNTER-INTUITIVE: Q1 safest = -0.5 (missed returns), Q4 = +1 (sweet spot)
    # Q5 riskiest = -1.0
    risk_scores = pd.Series(0.0, index=result.index)
    for col in RISK_SCORE_COLS:
        if col in result.columns:
            col_scores = _quintile_assign(
                result[col].where(mask),
                score_map=RISK_SCORES,
                nan_score=None,
            )
            risk_scores = risk_scores.add(col_scores.fillna(0), fill_value=0)

    result["risk_score"] = risk_scores

    # --- COMPOSITE ---
    result["composite_anjali_score"] = (
        result["growth_score"]
        + result["return_score"]
        + result["valuation_score"]
        + result["risk_score"]
    )

    # Round all scores
    for score_col in ["growth_score", "return_score", "valuation_score", "risk_score", "composite_anjali_score"]:
        result[score_col] = result[score_col].round(1)

    return result
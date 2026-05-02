"""
Walk-forward backtesting validator for NeuralQuant composite scores.
Computes forward-return accuracy, hit rates by score tier, Sharpe, and max drawdown.

Methodology:
- At each month-end, take composite_score for each stock
- Measure forward 1-month, 3-month, and 12-month returns
- Bin scores into deciles and compute hit rates (positive return %)
- Report Sharpe ratio, max drawdown, and accuracy at threshold scores

This mirrors walk-forward validation as described in Phase 1 spec and
provides the "backtested accuracy" metric competitors publish.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Summary statistics from walk-forward validation."""
    # Overall accuracy
    hit_rate_at_7plus: float       # % of stocks scoring >=7 that had positive forward 3M return
    hit_rate_at_5plus: float       # % of stocks scoring >=5 with positive forward 3M return
    baseline_hit_rate: float       # % of all stocks with positive forward 3M return (random)

    # Return statistics
    mean_return_top_decile: float   # Average forward 3M return of top-decile stocks
    mean_return_bottom_decile: float
    top_minus_bottom_spread: float  # Long-short spread

    # Risk metrics
    sharpe_top_quartile: float
    max_drawdown_top_quartile: float
    win_rate_top_quartile: float

    # Sample info
    observation_count: int
    period_start: str
    period_end: str
    avg_stocks_per_period: float


def run_walk_forward(
    score_history: pd.DataFrame,
    price_history: pd.DataFrame,
    forward_months: int = 3,
) -> BacktestResult:
    """
    Walk-forward backtest.

    Args:
        score_history: DataFrame with columns [date, ticker, composite_score, score_1_10]
                       One row per stock per rebalance date.
        price_history: DataFrame with columns [date, ticker, close]
                       Daily prices for computing forward returns.
        forward_months: Forward return horizon (1, 3, or 12).

    Returns:
        BacktestResult with summary statistics.
    """
    if score_history.empty or price_history.empty:
        raise ValueError("score_history and price_history must be non-empty")

    # Ensure date columns are datetime
    score_history["date"] = pd.to_datetime(score_history["date"])
    price_history["date"] = pd.to_datetime(price_history["date"])

    # Get unique rebalance dates
    rebalance_dates = sorted(score_history["date"].unique())

    all_hits = []  # (score_1_10, hit) tuples
    decile_returns: dict[int, list[float]] = {}  # decile → list of forward returns
    top_quartile_returns: list[float] = []

    total_obs = 0
    periods_with_data = 0

    for i, rd in enumerate(rebalance_dates):
        # Compute forward end date (approximate: forward_months * 21 trading days)
        forward_end = rd + pd.DateOffset(months=forward_months)

        # Get scores for this date
        scores = score_history[score_history["date"] == rd].copy()
        if scores.empty:
            continue

        # Get forward prices (closest trading day to forward_end)
        forward_prices = (
            price_history[price_history["date"] <= forward_end]
            .sort_values(["ticker", "date"])
            .groupby("ticker")
            .last()
            .reset_index()
        )

        # Get start prices (closest trading day to rd)
        start_prices = (
            price_history[price_history["date"] <= rd]
            .sort_values(["ticker", "date"])
            .groupby("ticker")
            .last()
            .reset_index()
        )

        # Merge to compute forward returns
        merged = scores.merge(
            start_prices[["ticker", "close"]].rename(columns={"close": "start_price"}),
            on="ticker",
            how="inner",
        )
        merged = merged.merge(
            forward_prices[["ticker", "close"]].rename(columns={"close": "end_price"}),
            on="ticker",
            how="inner",
        )

        if merged.empty:
            continue

        merged["forward_return"] = (merged["end_price"] - merged["start_price"]) / merged["start_price"]
        merged["hit"] = (merged["forward_return"] > 0).astype(int)
        merged["decile"] = pd.qcut(merged["composite_score"], q=10, labels=False, duplicates="drop")

        # Drop rows where decile is NaN (happens with tied scores)
        merged = merged.dropna(subset=["decile"])

        # Collect hit data
        for _, row in merged.iterrows():
            all_hits.append((row.get("score_1_10", row["composite_score"] * 10), int(row["hit"])))
            dec = int(row["decile"])
            decile_returns.setdefault(dec, []).append(float(row["forward_return"]))

        # Top quartile returns
        top_q = merged[merged["composite_score"] >= merged["composite_score"].quantile(0.75)]
        top_quartile_returns.extend(top_q["forward_return"].tolist())

        total_obs += len(merged)
        periods_with_data += 1

    if total_obs == 0:
        raise ValueError("No overlapping data between score and price history")

    # Compute hit rates
    hits_df = pd.DataFrame(all_hits, columns=["score", "hit"])
    hit_rate_7plus = hits_df[hits_df["score"] >= 7]["hit"].mean() if len(hits_df[hits_df["score"] >= 7]) > 0 else float("nan")
    hit_rate_5plus = hits_df[hits_df["score"] >= 5]["hit"].mean() if len(hits_df[hits_df["score"] >= 5]) > 0 else float("nan")
    baseline_hit_rate = hits_df["hit"].mean()

    # Decile returns
    top_decile = max(decile_returns.keys())
    bottom_decile = min(decile_returns.keys())
    mean_top = np.mean(decile_returns[top_decile])
    mean_bottom = np.mean(decile_returns[bottom_decile])

    # Risk metrics (top quartile)
    top_q_arr = np.array(top_quartile_returns)
    sharpe = float(np.mean(top_q_arr) / np.std(top_q_arr) * np.sqrt(12 / forward_months)) if np.std(top_q_arr) > 0 else 0.0
    peak = np.maximum.accumulate(top_q_arr)
    drawdowns = (peak - top_q_arr) / peak
    max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
    win_rate = float(np.mean(top_q_arr > 0))

    return BacktestResult(
        hit_rate_at_7plus=float(hit_rate_7plus) if not np.isnan(hit_rate_7plus) else 0.0,
        hit_rate_at_5plus=float(hit_rate_5plus) if not np.isnan(hit_rate_5plus) else 0.0,
        baseline_hit_rate=float(baseline_hit_rate),
        mean_return_top_decile=float(mean_top),
        mean_return_bottom_decile=float(mean_bottom),
        top_minus_bottom_spread=float(mean_top - mean_bottom),
        sharpe_top_quartile=float(sharpe),
        max_drawdown_top_quartile=float(max_dd),
        win_rate_top_quartile=float(win_rate),
        observation_count=total_obs,
        period_start=str(rebalance_dates[0].date()),
        period_end=str(rebalance_dates[-1].date()),
        avg_stocks_per_period=round(total_obs / periods_with_data, 1) if periods_with_data > 0 else 0.0,
    )


def compute_from_score_cache(score_cache_rows: list[dict], price_data: pd.DataFrame) -> BacktestResult:
    """
    Convenience wrapper that converts score_cache DB rows into the format
    expected by run_walk_forward.
    """
    score_history = pd.DataFrame(score_cache_rows)
    if "last_updated" in score_history.columns:
        score_history["date"] = pd.to_datetime(score_history["last_updated"]).dt.date
    elif "scored_at" in score_history.columns:
        score_history["date"] = pd.to_datetime(score_history["scored_at"]).dt.date
    elif "created_at" in score_history.columns:
        score_history["date"] = pd.to_datetime(score_history["created_at"]).dt.date
    else:
        score_history["date"] = pd.Timestamp.now().date()

    score_history["date"] = pd.to_datetime(score_history["date"])
    score_history["ticker"] = score_history["ticker"].str.upper()

    return run_walk_forward(score_history, price_data)

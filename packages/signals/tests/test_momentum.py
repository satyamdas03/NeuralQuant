import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta
from nq_signals.factors.momentum import compute_momentum_12_1, apply_crash_protection, compute_momentum_cross_sectional


def make_price_series(returns: list[float], start: date = date(2024, 1, 1)) -> pd.Series:
    prices = [100.0]
    for r in returns:
        prices.append(prices[-1] * (1 + r))
    idx = pd.date_range(start, periods=len(prices), freq="B")
    return pd.Series(prices, index=idx)


def test_momentum_12_1_positive():
    # Strong upward trend over 12 months
    prices = make_price_series([0.01] * 252)  # ~+12% cumulative return (approx)
    result = compute_momentum_12_1(prices)
    assert result > 0  # Positive momentum


def test_momentum_12_1_skips_last_month():
    # Classic 12-1: skip the most recent month (reversal effect)
    # Price up 11 months, down in last month — momentum should still be positive
    prices = make_price_series([0.01] * 231 + [-0.02] * 21)
    result = compute_momentum_12_1(prices)
    assert result > 0  # Still positive from 11 months of gains


def test_crash_protection_disables_momentum_in_bear():
    """In bear regime (SPX below 200MA), crash-protection flag should be True."""
    flag = apply_crash_protection(
        spx_return_1m=-0.15,
        spx_vs_200ma=-0.12,
    )
    assert flag is True  # Momentum signal should be suppressed


def test_crash_protection_off_in_bull():
    flag = apply_crash_protection(spx_return_1m=0.02, spx_vs_200ma=0.05)
    assert flag is False

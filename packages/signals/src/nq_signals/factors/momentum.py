import pandas as pd
import numpy as np


def compute_momentum_12_1(prices: pd.Series) -> float:
    """
    Classic 12-1 momentum: return from 12 months ago to 1 month ago.
    Skips most recent month to avoid short-term reversal contamination.
    Returns raw return (not percentile — caller handles cross-sectional ranking).
    """
    if len(prices) < 253:
        return float("nan")  # Need 252 days of lookback + 1 current price = 253 minimum
    # 252 trading days ≈ 12 months; 21 ≈ 1 month
    price_12m_ago = float(prices.iloc[-252])
    price_1m_ago = float(prices.iloc[-21])
    if price_12m_ago == 0:
        return float("nan")
    return (price_1m_ago - price_12m_ago) / price_12m_ago


def apply_crash_protection(
    spx_return_1m: float,
    spx_vs_200ma: float,
    drawdown_threshold: float = -0.10,
    ma_threshold: float = -0.05,
) -> bool:
    """
    Returns True when momentum should be suppressed (crash risk high).
    Triggers when SPX drops >10% in a month OR is >5% below its 200-day MA.
    Documented: momentum crashes most severely during sharp market reversals.
    """
    return spx_return_1m < drawdown_threshold or spx_vs_200ma < ma_threshold


def compute_momentum_cross_sectional(universe: pd.DataFrame,
                                     crash_flag: bool = False) -> pd.DataFrame:
    """
    Cross-sectional momentum ranking.
    universe: DataFrame with ticker, momentum_raw (from compute_momentum_12_1)
    Returns DataFrame with momentum_percentile column.
    If crash_flag is True, all momentum scores are set to 0.5 (neutral) — signal suppressed.
    """
    df = universe.copy()
    if crash_flag:
        df["momentum_percentile"] = 0.5
    else:
        df["momentum_percentile"] = df["momentum_raw"].rank(pct=True, na_option="keep")
        # NaN tickers (insufficient history) keep NaN — they are excluded from ranking
    return df

"""
Walk-forward cross-validation and IC/ICIR metrics.
Following Lopez de Prado (2018): train on T years, test on OOS.
"""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from .lgbm_ranker import SignalRanker


def compute_ic(df: pd.DataFrame, predicted_col: str,
               actual_col: str, group_col: str) -> pd.Series:
    """
    Information Coefficient (IC): Spearman rank correlation between
    predicted scores and actual next-period returns, computed per group.
    """
    ics = {}
    for period, group in df.groupby(group_col):
        pred = group[predicted_col].values
        actual = group[actual_col].values
        if len(pred) < 3:
            continue
        ic, _ = spearmanr(pred, actual)
        ics[period] = ic
    return pd.Series(ics)


def compute_icir(ic_series: pd.Series) -> float:
    """ICIR = IC mean / IC std. Target > 0.5; world-class > 1.0"""
    if ic_series.std() == 0:
        return 0.0
    return float(ic_series.mean() / ic_series.std())


def walk_forward_validate(df: pd.DataFrame, feature_cols: list[str],
                          target_col: str, period_col: str,
                          train_periods: int = 20,
                          test_periods: int = 4) -> dict:
    """
    Walk-forward validation following Lopez de Prado.
    Returns dict with IC series, ICIR, and hit rate per OOS period.
    """
    periods = sorted(df[period_col].unique())
    all_predictions = []

    for i in range(train_periods, len(periods) - test_periods + 1, test_periods):
        train_p = periods[i - train_periods: i]
        test_p = periods[i: i + test_periods]

        train_df = df[df[period_col].isin(train_p)]
        test_df = df[df[period_col].isin(test_p)].copy()

        ranker = SignalRanker()
        ranker.fit(train_df, feature_cols, target_col, period_col)
        test_df["predicted_score"] = ranker.predict(test_df)
        all_predictions.append(test_df)

    if not all_predictions:
        return {"ic": pd.Series(), "icir": 0.0, "hit_rate": 0.0}

    combined = pd.concat(all_predictions)
    ic = compute_ic(combined, "predicted_score", target_col, period_col)
    icir = compute_icir(ic)
    hit_rate = float((ic > 0).mean())

    return {"ic": ic, "icir": icir, "hit_rate": hit_rate,
            "ic_mean": float(ic.mean()), "ic_std": float(ic.std())}

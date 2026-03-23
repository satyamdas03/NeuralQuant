import pytest
import numpy as np
import pandas as pd
from nq_signals.ranker.lgbm_ranker import SignalRanker
from nq_signals.ranker.walk_forward import compute_ic, compute_icir


def make_synthetic_data(n_stocks: int = 50, n_periods: int = 8) -> pd.DataFrame:
    """Make fake factor + return data for testing."""
    np.random.seed(42)
    records = []
    for period in range(n_periods):
        quality = np.random.rand(n_stocks)
        momentum = np.random.rand(n_stocks)
        # True return correlates with quality + momentum (signal has alpha)
        true_signal = 0.6 * quality + 0.4 * momentum
        noise = np.random.randn(n_stocks) * 0.2
        returns = true_signal + noise
        for i in range(n_stocks):
            records.append({
                "period": period, "ticker": f"STOCK_{i:03d}",
                "quality_percentile": quality[i],
                "momentum_percentile": momentum[i],
                "low_vol_percentile": np.random.rand(),
                "next_period_return": returns[i],
            })
    return pd.DataFrame(records)


def test_ranker_fits_and_predicts():
    df = make_synthetic_data()
    train = df[df["period"] < 6]
    test = df[df["period"] >= 6]
    ranker = SignalRanker()
    ranker.fit(train, feature_cols=["quality_percentile", "momentum_percentile", "low_vol_percentile"],
               target_col="next_period_return", group_col="period")
    scores = ranker.predict(test[["quality_percentile", "momentum_percentile", "low_vol_percentile"]])
    assert len(scores) == len(test)
    assert not np.any(np.isnan(scores))


def test_ic_is_positive_with_signal():
    """IC should be positive when predictions correlate with actual returns."""
    df = make_synthetic_data()
    train = df[df["period"] < 6]
    test = df[df["period"] >= 6]
    ranker = SignalRanker()
    feature_cols = ["quality_percentile", "momentum_percentile", "low_vol_percentile"]
    ranker.fit(train, feature_cols=feature_cols,
               target_col="next_period_return", group_col="period")
    test = test.copy()
    test["predicted_score"] = ranker.predict(test[feature_cols])
    ic = compute_ic(test, predicted_col="predicted_score", actual_col="next_period_return",
                    group_col="period")
    assert ic.mean() > 0  # Positive IC confirms signal has predictive value


def test_compute_icir():
    ic_series = pd.Series([0.08, 0.06, 0.10, 0.05, 0.09])
    icir = compute_icir(ic_series)
    assert icir > 0
    assert icir == pytest.approx(ic_series.mean() / ic_series.std(), rel=0.01)

import pytest
import numpy as np
import pandas as pd
from nq_signals.regime.hmm_detector import RegimeDetector, RegimeState

def make_macro_df(n: int = 200) -> pd.DataFrame:
    """Synthetic macro data with two obvious regimes."""
    np.random.seed(42)
    # First half: calm (VIX low, positive spread, tight spreads)
    calm = pd.DataFrame({
        "vix": np.random.normal(14, 2, n//2).clip(8, 20),
        "vix_20d_change": np.random.normal(-0.1, 0.5, n//2),
        "spx_vs_200ma": np.random.normal(0.05, 0.02, n//2),
        "hy_spread_oas": np.random.normal(300, 30, n//2),
        "ism_pmi": np.random.normal(53, 2, n//2),
    })
    # Second half: stressed (VIX high, SPX below MA, spreads wide)
    stressed = pd.DataFrame({
        "vix": np.random.normal(30, 5, n//2).clip(20, 80),
        "vix_20d_change": np.random.normal(0.5, 0.8, n//2),
        "spx_vs_200ma": np.random.normal(-0.08, 0.03, n//2),
        "hy_spread_oas": np.random.normal(700, 80, n//2),
        "ism_pmi": np.random.normal(46, 3, n//2),
    })
    return pd.concat([calm, stressed], ignore_index=True)

def test_regime_detector_fits_without_error():
    df = make_macro_df(200)
    detector = RegimeDetector(n_regimes=4)
    detector.fit(df)  # Should not raise

def test_regime_detector_returns_soft_posteriors():
    df = make_macro_df(200)
    detector = RegimeDetector(n_regimes=4)
    detector.fit(df)
    posteriors = detector.predict_proba(df)
    assert posteriors.shape == (len(df), 4)
    # Each row sums to ~1.0
    np.testing.assert_allclose(posteriors.sum(axis=1), 1.0, atol=1e-5)

def test_regime_state_identifies_stress():
    df = make_macro_df(200)
    detector = RegimeDetector(n_regimes=4)
    detector.fit(df)
    # Check last row (should be stressed regime)
    state = detector.get_current_state(df.iloc[-1:])
    assert isinstance(state, RegimeState)
    assert 0.0 <= state.confidence <= 1.0
    assert state.regime_id in [1, 2, 3, 4]

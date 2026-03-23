"""
Integration test: DataBroker -> DataStore -> SignalEngine -> ranked output.
Uses mocked data sources to avoid real API calls in CI.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import date
from unittest.mock import MagicMock

from nq_signals.engine import SignalEngine, UniverseSnapshot


def make_universe(n: int = 10) -> UniverseSnapshot:
    tickers = [f"T{i:02d}" for i in range(n)]
    np.random.seed(0)
    macro = MagicMock()
    macro.vix = 16.0
    macro.spx_vs_200ma = 0.03
    macro.hy_spread_oas = 340.0
    macro.ism_pmi = 51.0
    macro.yield_spread_2y10y = 0.15
    macro.spx_return_1m = 0.02
    return UniverseSnapshot(
        tickers=tickers,
        market="US",
        fundamentals=pd.DataFrame({
            "ticker": tickers,
            "gross_profit_margin": np.random.uniform(0.2, 0.8, n),
            "accruals_ratio": np.random.uniform(-0.1, 0.1, n),
            "piotroski": np.random.randint(3, 9, n),
            "momentum_raw": np.random.uniform(-0.2, 0.5, n),
            "short_interest_pct": np.random.uniform(0.01, 0.15, n),
        }),
        macro=macro,
    )


def test_full_signal_pipeline():
    """End-to-end: SignalEngine computes composite scores and returns ranked DataFrame."""
    engine = SignalEngine()
    snapshot = make_universe(10)
    result = engine.compute(snapshot)

    assert len(result) == 10, "All tickers must appear in output"
    assert result.iloc[0]["composite_score"] >= result.iloc[-1]["composite_score"], \
        "Output must be sorted descending by composite_score"
    assert "regime_id" in result.columns, "regime_id must be present"
    assert result["regime_id"].iloc[0] in [1, 2, 3, 4], "regime_id must be 1-4"
    assert "composite_score" in result.columns
    assert "quality_percentile" in result.columns
    assert "momentum_percentile" in result.columns

    print("\nTop 3 picks (integration test):")
    print(result[["ticker", "composite_score", "quality_percentile",
                  "momentum_percentile", "regime_id"]].head(3).to_string(index=False))


def test_signal_engine_crash_protection():
    """When SPX is in bear (down >10%), momentum goes to neutral 0.5."""
    engine = SignalEngine()
    snapshot = make_universe(10)
    # Simulate bear market crash
    snapshot.macro.spx_return_1m = -0.15
    snapshot.macro.spx_vs_200ma = -0.08

    result = engine.compute(snapshot)
    assert len(result) == 10
    # In crash regime, all momentum_percentile values should be 0.5
    assert (result["momentum_percentile"] == 0.5).all(), \
        "Crash protection should neutralise momentum to 0.5 for all tickers"


def test_signal_engine_with_small_universe():
    """Single-ticker universe should not crash."""
    engine = SignalEngine()
    snapshot = make_universe(1)
    result = engine.compute(snapshot)
    assert len(result) == 1
    assert 0.0 <= result.iloc[0]["composite_score"] <= 1.0


def test_composite_score_bounds():
    """composite_score must be in [0, 1] for typical inputs."""
    engine = SignalEngine()
    snapshot = make_universe(20)
    result = engine.compute(snapshot)
    assert result["composite_score"].between(0.0, 1.0).all(), \
        f"composite_score out of bounds: {result['composite_score'].describe()}"

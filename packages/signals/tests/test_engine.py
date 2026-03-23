import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from nq_signals.engine import SignalEngine, UniverseSnapshot


def make_mock_snapshot() -> UniverseSnapshot:
    tickers = [f"STOCK_{i}" for i in range(20)]
    return UniverseSnapshot(
        tickers=tickers,
        market="US",
        fundamentals=pd.DataFrame({
            "ticker": tickers,
            "gross_profit_margin": [0.4 + i*0.01 for i in range(20)],
            "accruals_ratio": [-0.02 - i*0.001 for i in range(20)],
            "piotroski": [5 + i % 4 for i in range(20)],
            "momentum_raw": [0.1 + i*0.01 for i in range(20)],
            "short_interest_pct": [0.05 - i*0.001 for i in range(20)],
        }),
        macro=MagicMock(vix=15.0, spx_vs_200ma=0.05, hy_spread_oas=320.0,
                        ism_pmi=52.0, yield_spread_2y10y=0.2),
    )


def test_engine_returns_ranked_universe():
    engine = SignalEngine()
    snapshot = make_mock_snapshot()
    with patch.object(engine, "_get_regime", return_value=MagicMock(
        regime_id=1, confidence=0.82,
        factor_weights={"momentum": 0.30, "quality": 0.25, "value": 0.10,
                        "low_vol": 0.10, "growth": 0.25},
        posteriors=[0.82, 0.1, 0.05, 0.03],
    )):
        result = engine.compute(snapshot)
    assert "ticker" in result.columns
    assert "composite_score" in result.columns
    assert len(result) == 20
    assert result["composite_score"].is_monotonic_decreasing  # Ranked high→low

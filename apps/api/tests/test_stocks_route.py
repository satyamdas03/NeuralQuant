from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import pandas as pd
from nq_api.main import app
from nq_api.deps import get_signal_engine

client = TestClient(app)

def _mock_engine_result():
    """Minimal engine output for a single ticker."""
    return pd.DataFrame([{
        "ticker": "AAPL",
        "composite_score": 0.78,
        "quality_percentile": 0.85,
        "momentum_percentile": 0.70,
        "short_interest_percentile": 0.60,
        "regime_id": 1,
    }])


def test_get_stock_score_returns_ai_score():
    engine = MagicMock()
    engine.compute.return_value = _mock_engine_result()
    app.dependency_overrides[get_signal_engine] = lambda: engine
    try:
        response = client.get("/stocks/AAPL?market=US")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "AAPL"
        assert 1 <= data["score_1_10"] <= 10
        assert data["regime_label"] in ["Risk-On", "Late-Cycle", "Bear", "Recovery"]
        assert len(data["top_drivers"]) >= 3
        assert "sub_scores" in data
    finally:
        app.dependency_overrides.pop(get_signal_engine, None)


def test_get_stock_score_unknown_ticker_returns_404():
    engine = MagicMock()
    engine.compute.return_value = pd.DataFrame()
    app.dependency_overrides[get_signal_engine] = lambda: engine
    try:
        response = client.get("/stocks/FAKE999?market=US")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_signal_engine, None)

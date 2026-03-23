# apps/api/tests/test_screener_route.py
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from nq_api.main import app
from nq_api.deps import get_signal_engine

client = TestClient(app)


def _mock_engine_for_universe(n_tickers: int):
    tickers = [f"T{i:02d}" for i in range(n_tickers)]
    np.random.seed(42)
    return pd.DataFrame([{
        "ticker": t,
        "composite_score": np.random.uniform(0.2, 0.9),
        "quality_percentile": np.random.uniform(0, 1),
        "momentum_percentile": np.random.uniform(0, 1),
        "short_interest_percentile": np.random.uniform(0, 1),
        "regime_id": 1,
    } for t in tickers])


def test_screener_returns_ranked_list():
    engine = MagicMock()
    engine.compute.return_value = _mock_engine_for_universe(10)
    app.dependency_overrides[get_signal_engine] = lambda: engine
    try:
        response = client.post("/screener", json={"market": "US", "max_results": 5})
        assert response.status_code == 200

        data = response.json()
        assert "results" in data
        assert len(data["results"]) <= 5

        scores = [r["composite_score"] for r in data["results"]]
        assert scores == sorted(scores, reverse=True), "Must be sorted descending"
    finally:
        app.dependency_overrides.clear()


def test_screener_filters_by_min_score():
    engine = MagicMock()
    engine.compute.return_value = _mock_engine_for_universe(10)
    app.dependency_overrides[get_signal_engine] = lambda: engine
    try:
        response = client.post("/screener", json={"market": "US", "min_score": 0.8})
        assert response.status_code == 200

        data = response.json()
        for r in data["results"]:
            assert r["composite_score"] >= 0.8
    finally:
        app.dependency_overrides.clear()

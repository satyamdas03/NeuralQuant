# apps/api/tests/test_screener_route.py
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
from nq_api.main import app
from nq_api.deps import get_signal_engine
from nq_api.routes.screener import _is_merged_market, _read_top_merged, _read_top_for_screener
import nq_api.routes.screener as screener_module

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


def _mock_snapshot(*args, **kwargs):
    return []


def test_screener_returns_ranked_list():
    engine = MagicMock()
    engine.compute.return_value = _mock_engine_for_universe(10)
    app.dependency_overrides[get_signal_engine] = lambda: engine
    try:
        with patch("nq_api.routes.screener.build_real_snapshot", side_effect=_mock_snapshot):
            response = client.post("/screener", json={"market": "US", "max_results": 5})
        assert response.status_code == 200

        data = response.json()
        assert "results" in data
        assert len(data["results"]) <= 5

        scores = [r["composite_score"] for r in data["results"]]
        assert scores == sorted(scores, reverse=True), "Must be sorted descending"
    finally:
        app.dependency_overrides.pop(get_signal_engine, None)


def test_screener_filters_by_min_score():
    engine = MagicMock()
    engine.compute.return_value = _mock_engine_for_universe(10)
    app.dependency_overrides[get_signal_engine] = lambda: engine
    try:
        with patch("nq_api.routes.screener.build_real_snapshot", side_effect=_mock_snapshot), \
             patch("nq_api.routes.screener._read_top_for_screener", return_value=[]):
            response = client.post("/screener", json={"market": "US", "min_score": 0.8})
        assert response.status_code == 200

        data = response.json()
        for r in data["results"]:
            assert r["composite_score"] >= 0.8
    finally:
        app.dependency_overrides.pop(get_signal_engine, None)


def test_read_top_merged_backfills_change_pct_from_snapshot():
    us_rows = [
        {"ticker": "AAPL", "market": "US", "composite_score": 80.0},
    ]
    in_rows = [
        {"ticker": "RELIANCE.NS", "market": "IN", "composite_score": 90.0},
    ]
    us_snaps = [
        {"ticker": "AAPL", "market": "US", "change_pct": 1.25, "price": 175.5, "company_name": "Apple Inc."},
    ]
    in_snaps = [
        {"ticker": "RELIANCE", "market": "IN", "change_pct": -0.75, "price": 2450.0, "company_name": "Reliance Industries"},
    ]

    def _batch_snapshots(tickers, market):
        return us_snaps if market == "US" else in_snaps

    with patch.object(screener_module, "score_cache") as mock_cache, \
         patch.object(screener_module, "read_snapshot_batch", side_effect=_batch_snapshots):
        mock_cache.read_top.side_effect = [us_rows, in_rows]
        merged = _read_top_merged(3, 300)
    assert len(merged) == 2
    assert merged[0]["ticker"] == "RELIANCE.NS"
    assert merged[0]["change_pct"] == -0.75
    assert merged[0]["current_price"] == 2450.0
    assert merged[0]["long_name"] == "Reliance Industries"
    assert merged[1]["ticker"] == "AAPL"
    assert merged[1]["change_pct"] == 1.25
    assert merged[1]["current_price"] == 175.5
    assert merged[1]["long_name"] == "Apple Inc."


def test_read_top_for_screener_backfills_change_pct_single_market():
    rows = [
        {"ticker": "AAPL", "market": "US", "composite_score": 80.0},
    ]
    snaps = [
        {"ticker": "AAPL", "market": "US", "change_pct": 2.0, "price": 180.0, "company_name": "Apple Inc."},
    ]
    with patch.object(screener_module, "score_cache") as mock_cache, \
         patch.object(screener_module, "read_snapshot_batch", return_value=snaps):
        mock_cache.read_top.return_value = rows
        result = _read_top_for_screener("US", 5, 300)
    assert len(result) == 1
    assert result[0]["change_pct"] == 2.0
    assert result[0]["current_price"] == 180.0


def test_screener_both_returns_change_pct():
    cached = [
        {"ticker": "AAPL", "market": "US", "composite_score": 80.0, "score_1_10": 8, "regime_id": 1},
        {"ticker": "RELIANCE.NS", "market": "IN", "composite_score": 90.0, "score_1_10": 9, "regime_id": 1},
    ]
    us_snaps = [
        {"ticker": "AAPL", "market": "US", "change_pct": 1.5, "price": 176.0, "company_name": "Apple Inc."},
    ]
    in_snaps = [
        {"ticker": "RELIANCE", "market": "IN", "change_pct": -1.0, "price": 2440.0, "company_name": "Reliance Industries"},
    ]

    def _batch_snapshots(tickers, market):
        return us_snaps if market == "US" else in_snaps

    with patch.object(screener_module, "score_cache") as mock_cache, \
         patch.object(screener_module, "read_snapshot_batch", side_effect=_batch_snapshots):
        mock_cache.read_top.side_effect = [cached[:1], cached[1:]]
        response = client.post("/screener", json={"market": "BOTH", "max_results": 10})
    assert response.status_code == 200
    data = response.json()
    by_ticker = {r["ticker"]: r for r in data["results"]}
    assert "AAPL" in by_ticker
    assert "RELIANCE.NS" in by_ticker
    assert by_ticker["AAPL"]["change_pct"] == 1.5
    assert by_ticker["RELIANCE.NS"]["change_pct"] == -1.0


def test_is_merged_market():
    assert _is_merged_market("BOTH") is True
    assert _is_merged_market("GLOBAL") is True
    assert _is_merged_market("US") is False
    assert _is_merged_market("IN") is False


def test_read_top_merged_sorts_and_limits():
    us_rows = [
        {"ticker": "AAPL", "market": "US", "composite_score": 80.0},
        {"ticker": "MSFT", "market": "US", "composite_score": 60.0},
    ]
    in_rows = [
        {"ticker": "RELIANCE", "market": "IN", "composite_score": 90.0},
        {"ticker": "TCS", "market": "IN", "composite_score": 70.0},
    ]
    with patch.object(screener_module, "score_cache") as mock_cache, \
         patch.object(screener_module, "read_snapshot_batch", return_value=[]):
        mock_cache.read_top.side_effect = [us_rows, in_rows]
        merged = _read_top_merged(3, 300)
    assert len(merged) == 3
    assert merged[0]["ticker"] == "RELIANCE"
    assert merged[1]["ticker"] == "AAPL"
    assert merged[2]["ticker"] == "TCS"

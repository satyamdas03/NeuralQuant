from dataclasses import dataclass
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
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


@dataclass
class MockSnapshot:
    """Minimal mock of UniverseSnapshot with fundamentals attribute."""
    tickers: list
    market: str
    fundamentals: pd.DataFrame
    macro: object = None


def _mock_snapshot(*args, **kwargs):
    """Return a mock UniverseSnapshot with non-empty fundamentals."""
    return MockSnapshot(
        tickers=["AAPL"],
        market="US",
        fundamentals=pd.DataFrame([{
            "ticker": "AAPL",
            "composite_score": 0.78,
            "quality_percentile": 0.85,
            "momentum_percentile": 0.70,
            "short_interest_percentile": 0.60,
            "regime_id": 1,
        }]),
    )


def _mock_snapshot_empty(*args, **kwargs):
    """Return a mock UniverseSnapshot with empty fundamentals (unknown ticker)."""
    return MockSnapshot(
        tickers=["FAKE999"],
        market="US",
        fundamentals=pd.DataFrame(),
    )


def test_get_stock_score_returns_ai_score():
    engine = MagicMock()
    engine.compute.return_value = _mock_engine_result()
    app.dependency_overrides[get_signal_engine] = lambda: engine
    try:
        with patch("nq_api.routes.stocks.build_real_snapshot", side_effect=_mock_snapshot), \
             patch("nq_api.routes.stocks.score_cache") as mock_cache:
            mock_cache.read_one.return_value = None  # Force cache miss → live compute
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


def test_get_stock_score_in_fallback_name_from_universe():
    """IN ticker with a placeholder name resolves via static universe JSON."""
    from unittest.mock import patch, MagicMock

    engine = MagicMock()
    app.dependency_overrides[get_signal_engine] = lambda: engine
    cached = {
        "ticker": "TCS.NS",
        "market": "IN",
        "composite_score": 65.0,
        "score_1_10": 8,
        "regime_id": 1,
        "long_name": "TCS.NS",  # placeholder equal to ticker
        "current_price": 3500.0,
        "change_pct": 1.2,
    }
    try:
        with patch("nq_api.routes.stocks.score_cache.read_one", return_value=cached), \
             patch("nq_api.routes.stocks._read_stock_snapshot", return_value={
                 "ticker": "TCS", "market": "IN", "company_name": None,
                 "price": 3500.0, "change_pct": 1.2,
             }):
            response = client.get("/stocks/TCS.NS?market=IN")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "TCS.NS"
        assert data["name"] == "Tata Consultancy Services Ltd."
    finally:
        app.dependency_overrides.pop(get_signal_engine, None)


def test_get_stock_score_in_name_from_snapshot_company_name():
    """IN ticker cache name backfilled from stock_snapshot.company_name."""
    from unittest.mock import patch, MagicMock

    engine = MagicMock()
    app.dependency_overrides[get_signal_engine] = lambda: engine
    cached = {
        "ticker": "RELIANCE.NS",
        "market": "IN",
        "composite_score": 50.0,
        "score_1_10": 6,
        "regime_id": 1,
        "current_price": None,  # forces snapshot backfill so name is read too
        "change_pct": 0.5,
    }
    try:
        with patch("nq_api.routes.stocks.score_cache.read_one", return_value=cached), \
             patch("nq_api.routes.stocks._read_stock_snapshot", return_value={
                 "ticker": "RELIANCE", "market": "IN",
                 "company_name": "Reliance Industries Limited",
                 "price": 2450.0, "change_pct": 0.5,
             }):
            response = client.get("/stocks/RELIANCE.NS?market=IN")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Reliance Industries Limited"
    finally:
        app.dependency_overrides.pop(get_signal_engine, None)


def test_get_stock_meta_in_fallback_name_from_universe():
    """Meta endpoint falls back to static universe mapping for IN names."""
    from unittest.mock import patch

    snap = {
        "ticker": "TCS", "market": "IN", "company_name": None,
        "price": 3500.0, "change_pct": 1.2,
        "sector": "Information Technology", "sub_sector": "IT Services",
    }
    with patch("nq_api.routes.stocks._read_stock_snapshot", return_value=snap), \
         patch("nq_api.routes.stocks._fetch_stock_meta_fmp_light", return_value=None), \
         patch("nq_api.routes.stocks._fetch_stock_meta", return_value=None), \
         patch("nq_api.routes.stocks._read_score_cache", return_value=None):
        response = client.get("/stocks/TCS.NS/meta?market=IN")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Tata Consultancy Services Ltd."


def test_get_stock_score_unknown_ticker_returns_404():
    engine = MagicMock()
    engine.compute.return_value = pd.DataFrame()
    app.dependency_overrides[get_signal_engine] = lambda: engine
    try:
        with patch("nq_api.routes.stocks.build_real_snapshot", side_effect=_mock_snapshot_empty), \
             patch("nq_api.routes.stocks.score_cache") as mock_cache:
            mock_cache.read_one.return_value = None  # Force cache miss → live compute
            response = client.get("/stocks/FAKE999?market=US")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_signal_engine, None)
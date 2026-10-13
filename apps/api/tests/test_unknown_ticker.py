"""Regression tests for F-02: unknown tickers must return 404, never score 10.

Before the fix, GET /stocks/NOTAREALTICKERXYZ?market=US could return 200 with
score_1_10=10 because the endpoint would accept any ticker that upstream data
sources happened to answer for, or because a 1-row universe percentile rank
mapped to the top decile.
"""

import pytest
from fastapi.testclient import TestClient

from nq_api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_unknown_us_ticker_returns_404(client):
    resp = client.get("/stocks/NOTAREALTICKERXYZ?market=US")
    assert resp.status_code == 404
    assert "No data" in resp.json()["detail"] or "Unknown ticker" in resp.json()["detail"]


def test_unknown_in_ticker_returns_404(client):
    resp = client.get("/stocks/NOTAREALTICKERXYZ?market=IN")
    assert resp.status_code == 404


def test_unknown_both_market_returns_404(client):
    resp = client.get("/stocks/NOTAREALTICKERXYZ?market=BOTH")
    assert resp.status_code == 404


def test_known_us_ticker_accepts_request(client, monkeypatch):
    """A known ticker (AAPL) passes universe validation and is served from cache.
    We patch score_cache.read_one to return a minimal valid row so we never hit
    the slow path (which would need real network I/O and a real signal engine)."""
    from nq_api.cache import score_cache

    def fake_read_one(ticker, market, max_age_seconds=None):
        return {
            "ticker": ticker,
            "market": market,
            "composite_score": 0.5,
            "regime_id": 1,
            "current_price": 150.0,
            "change_pct": 1.0,
            "long_name": "Apple Inc.",
        }

    monkeypatch.setattr(score_cache, "read_one", fake_read_one)

    resp = client.get("/stocks/AAPL?market=US")
    assert resp.status_code == 200
    assert "Unknown ticker" not in resp.json().get("detail", "")
    assert resp.json()["ticker"] == "AAPL"

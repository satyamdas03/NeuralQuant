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


# --- S2: /meta uses the same universe check and message as the score route ---

@pytest.mark.parametrize("market", ["US", "IN", "BOTH"])
def test_unknown_ticker_meta_returns_404(client, market):
    resp = client.get(f"/stocks/NOTAREALTICKERXYZ/meta?market={market}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Unknown ticker NOTAREALTICKERXYZ"


def test_meta_and_score_404_messages_match(client):
    score = client.get("/stocks/NOTAREALTICKERXYZ?market=US")
    meta = client.get("/stocks/NOTAREALTICKERXYZ/meta?market=US")
    assert score.status_code == meta.status_code == 404
    assert score.json()["detail"] == meta.json()["detail"]


def test_known_ticker_meta_passes_universe_check(client, monkeypatch):
    """AAPL is in the US universe, so /meta goes on to the data lookup."""
    from nq_api.routes import stocks

    async def fake_inner(t_up, market, snap, read_snapshot=False):
        return {"ticker": t_up, "name": "Apple Inc."}

    monkeypatch.setattr(stocks, "_get_stock_meta_inner", fake_inner)
    resp = client.get("/stocks/AAPL/meta?market=US")
    assert resp.status_code == 200
    assert resp.json()["ticker"] == "AAPL"


# --- One-row composite: absolute mapping, not a 1-row percentile rank ---

@pytest.mark.parametrize("composite,expected", [(0.0, 1), (0.75, 10)])
def test_one_row_composite_maps_to_absolute_score(composite, expected):
    import pandas as pd
    from nq_api.score_builder import _score_to_1_10, rank_scores_in_universe

    assert _score_to_1_10(composite) == expected
    # The 1-row percentile rank always gives 10; the live path must not use it.
    one_row = pd.DataFrame({"ticker": ["AAPL"], "composite_score": [composite]})
    assert int(rank_scores_in_universe(one_row).iloc[0]) == 10


@pytest.mark.parametrize("composite,expected", [(0.0, 1), (0.75, 10)])
def test_one_row_live_path_score(client, monkeypatch, composite, expected):
    """Cache miss -> live compute on a one-row universe. Score follows the
    composite (0.0 -> 1, 0.75 -> 10), not the percentile rank."""
    import pandas as pd
    from types import SimpleNamespace
    from nq_api.cache import score_cache
    from nq_api.deps import get_signal_engine
    from nq_api.routes import stocks

    monkeypatch.setattr(score_cache, "read_one", lambda *a, **k: None)
    monkeypatch.setattr(
        stocks,
        "build_real_snapshot",
        lambda tickers, market: SimpleNamespace(fundamentals=pd.DataFrame({"ticker": tickers})),
    )

    class OneRowEngine:
        def compute(self, snapshot):
            return pd.DataFrame(
                {"ticker": ["AAPL"], "composite_score": [composite], "regime_id": [1]}
            )

    app.dependency_overrides[get_signal_engine] = lambda: OneRowEngine()
    try:
        resp = client.get("/stocks/AAPL?market=US")
    finally:
        app.dependency_overrides.pop(get_signal_engine, None)
    assert resp.status_code == 200, resp.text
    assert resp.json()["score_1_10"] == expected

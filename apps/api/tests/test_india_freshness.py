"""Regression tests for F-01: India snapshot freshness must come from cached_at.

Before the fix, Indian stock pages showed weeks-old prices with stale=false because
`_snapshot_to_meta` copied the stored `stale` flag. The score endpoint also
backfilled stale snapshot prices into cached score rows.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from nq_api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _fresh_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stale_ts() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()


def test_in_meta_computes_stale_from_cached_at(client):
    """A stored stale=false does not override a weeks-old cached_at for IN."""
    snap = {
        "ticker": "TCS",
        "market": "IN",
        "company_name": "Tata Consultancy Services Limited",
        "price": 2348.0,
        "change_pct": 1.0,
        "cached_at": _stale_ts(),
        "stale": False,  # lie, as seen in audit
    }
    with patch("nq_api.routes.stocks._read_stock_snapshot", return_value=snap), \
         patch("nq_api.routes.stocks._fetch_stock_meta_fmp_light", return_value=None), \
         patch("nq_api.routes.stocks._fetch_stock_meta", return_value=None), \
         patch("nq_api.routes.stocks._read_score_cache", return_value=None):
        resp = client.get("/stocks/TCS.NS/meta?market=IN")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stale"] is True
    assert data["cached_at"] == snap["cached_at"]


def test_in_meta_fresh_snapshot_not_stale(client):
    """A recent cached_at produces stale=false."""
    snap = {
        "ticker": "TCS",
        "market": "IN",
        "company_name": "Tata Consultancy Services Limited",
        "price": 2156.0,
        "change_pct": -0.5,
        "cached_at": _fresh_ts(),
        "stale": False,
    }
    with patch("nq_api.routes.stocks._read_stock_snapshot", return_value=snap), \
         patch("nq_api.routes.stocks._fetch_stock_meta_fmp_light", return_value=None), \
         patch("nq_api.routes.stocks._fetch_stock_meta", return_value=None), \
         patch("nq_api.routes.stocks._read_score_cache", return_value=None):
        resp = client.get("/stocks/TCS.NS/meta?market=IN")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stale"] is False


def test_in_score_skips_stale_snapshot_price_backfill(client, monkeypatch):
    """The score endpoint must not backfill current_price from a stale IN snapshot."""
    from nq_api.cache import score_cache

    cached = {
        "ticker": "RELIANCE",
        "market": "IN",
        "composite_score": 50.0,
        "score_1_10": 6,
        "regime_id": 1,
        "current_price": None,  # triggers snapshot backfill
        "change_pct": 1.5,      # keeps yfinance fallback from firing
        "long_name": None,
    }

    stale_snap = {
        "ticker": "RELIANCE",
        "market": "IN",
        "company_name": "Reliance Industries Limited",
        "price": 1313131.0,  # stale/wrong price
        "change_pct": 99.9,
        "cached_at": _stale_ts(),
    }

    def fake_read_one(ticker, market, max_age_seconds=None):
        return cached

    def fake_read_snapshot(ticker, market):
        return stale_snap

    monkeypatch.setattr(score_cache, "read_one", fake_read_one)
    monkeypatch.setattr("nq_api.routes.stocks._read_stock_snapshot", fake_read_snapshot)
    monkeypatch.setattr("nq_api.routes.stocks._fetch_stock_meta", lambda t, m: None)

    resp = client.get("/stocks/RELIANCE.NS?market=IN")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_price"] != 1313131.0
    assert data["change_pct"] == 1.5
    assert data["name"] == "Reliance Industries Ltd."

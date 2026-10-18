"""Regression tests for F-01 and F-14: India quote freshness and card/meta agreement.

Audited failure (live 2026-10-17): GET /stocks/TCS/meta?market=IN returned
HTTP 200 with current_price 2348.0, cached_at 2026-09-03 and stale:false. The
card (GET /stocks/TCS?market=IN) showed name "TCS.NS", market cap 0, a different
P/E, and last_updated equal to the request clock.

Rules under test:
- IN stale = more than 36 weekday hours (Mon-Fri, IST) since cached_at.
- A stale quote carries no numeric price; a stored stale=false never wins.
- Card and meta resolve name, price, market cap and P/E through one resolver.
- Card last_updated is the score row's data time, not the request clock.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from nq_api.main import app
from nq_api.quote_freshness import (
    IN_STALE_WEEKDAY_HOURS,
    in_quote_is_stale,
    resolve_in_quote,
    weekday_hours_between,
)

IST = timezone(timedelta(hours=5, minutes=30))


def _ist(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=IST)


# ── Frozen-clock unit tests ────────────────────────────────────────────────
# 2026-10-16 is a Friday, 2026-10-19 a Monday.

def test_threshold_is_36_weekday_hours():
    assert IN_STALE_WEEKDAY_HOURS == 36


def test_weekend_does_not_count():
    # Saturday morning to Sunday night: zero weekday hours.
    assert weekday_hours_between(_ist(2026, 10, 17, 9), _ist(2026, 10, 18, 23)) == 0.0


def test_friday_close_fresh_on_monday_morning():
    cached = _ist(2026, 10, 16, 15, 30).isoformat()
    now = _ist(2026, 10, 19, 9, 15)
    # 8.5h Friday evening + 9.25h Monday = 17.75 weekday hours
    assert weekday_hours_between(_ist(2026, 10, 16, 15, 30), now) == pytest.approx(17.75)
    assert in_quote_is_stale(cached, now=now) is False


def test_missed_friday_session_is_stale_on_monday_morning():
    # Thursday close, feeder misses Friday: 8.5 + 24 + 9.25 = 41.75 > 36.
    cached = _ist(2026, 10, 15, 15, 30).isoformat()
    assert in_quote_is_stale(cached, now=_ist(2026, 10, 19, 9, 15)) is True


def test_more_than_36_weekday_hours_is_stale():
    cached = _ist(2026, 10, 19, 10).isoformat()  # Monday 10:00
    assert in_quote_is_stale(cached, now=_ist(2026, 10, 20, 21)) is False  # 35h
    assert in_quote_is_stale(cached, now=_ist(2026, 10, 20, 23)) is True   # 37h


def test_missing_or_bad_cached_at_is_stale():
    now = _ist(2026, 10, 19, 12)
    assert in_quote_is_stale(None, now=now) is True
    assert in_quote_is_stale("not-a-date", now=now) is True


def test_resolver_strips_price_when_stale():
    snap = {"ticker": "TCS", "company_name": "Tata Consultancy Services Limited",
            "price": 2348.0, "change_pct": -0.89, "market_cap": 8918585573376,
            "pe_ttm": 17.4, "cached_at": "2026-09-03T01:04:47.299141+00:00", "stale": False}
    q = resolve_in_quote("TCS", snap, None, now=_ist(2026, 10, 18, 10))
    assert q["stale"] is True
    assert q["quote_status"] == "quote_stale"
    assert q["current_price"] is None
    assert q["change_pct"] is None
    assert q["name"] == "Tata Consultancy Services Limited"


# ── Route tests ────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    return TestClient(app)


def _fresh_ts() -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()


def _stale_ts() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()


SCORE_COMPUTED_AT = "2026-10-17T02:00:00+00:00"


def _tcs_snap(cached_at: str) -> dict:
    return {
        "ticker": "TCS",
        "market": "IN",
        "company_name": "Tata Consultancy Services Limited",
        "price": 2348.0,
        "change_pct": -0.89,
        "market_cap": 8918585573376,
        "pe_ttm": 17.4,
        "cached_at": cached_at,
        "stale": False,  # stored flag lies, as seen in the audit
    }


def _tcs_score_row() -> dict:
    # Shape of the live card source: placeholder name, mcap 0, different P/E.
    return {
        "ticker": "TCS.NS",
        "market": "IN",
        "composite_score": 50.0,
        "score_1_10": 5,
        "regime_id": 1,
        "current_price": 2348.0,
        "change_pct": None,
        "long_name": "TCS.NS",
        "market_cap": 0,
        "pe_ttm": 14.9,
        "computed_at": SCORE_COMPUTED_AT,
    }


def _patches(snap: dict, row: dict):
    """Isolate both routes from Supabase, FMP, yfinance and live price."""
    def read_one(ticker, market, max_age_seconds=None):
        return dict(row)

    return [
        patch("nq_api.routes.stocks._read_stock_snapshot", return_value=dict(snap)),
        patch("nq_api.routes.stocks.score_cache.read_one", side_effect=read_one),
        patch("nq_api.routes.stocks._fetch_stock_meta_fmp_light", return_value=None),
        patch("nq_api.routes.stocks._fetch_stock_meta_fmp", return_value=None),
        patch("nq_api.routes.stocks._fetch_stock_meta", return_value=None),
        patch("nq_api.services.live_price.get_live_price", return_value=(2348.0, "score_cache")),
        patch("nq_api.score_builder.get_anjali_enrichment", return_value=None),
    ]


def _get(client, path, snap, row):
    ps = _patches(snap, row)
    for p in ps:
        p.start()
    try:
        return client.get(path)
    finally:
        for p in reversed(ps):
            p.stop()


def test_in_meta_stale_row_has_no_price(client):
    """Fails on the old behaviour: 200 with price 2348 for a 7-day-old row."""
    snap = _tcs_snap(_stale_ts())
    resp = _get(client, "/stocks/TCS.NS/meta?market=IN", snap, _tcs_score_row())
    assert resp.status_code == 200
    data = resp.json()
    assert data["stale"] is True
    assert data["quote_status"] == "quote_stale"
    assert data["current_price"] is None
    assert data["change_pct"] is None
    assert data["cached_at"] == snap["cached_at"]
    assert "2348" not in resp.text


def test_in_meta_fresh_row_has_price(client):
    snap = _tcs_snap(_fresh_ts())
    resp = _get(client, "/stocks/TCS.NS/meta?market=IN", snap, _tcs_score_row())
    assert resp.status_code == 200
    data = resp.json()
    assert data["stale"] is False
    assert data["quote_status"] == "ok"
    assert data["current_price"] == 2348.0


def test_in_card_stale_row_has_no_price(client):
    snap = _tcs_snap(_stale_ts())
    resp = _get(client, "/stocks/TCS?market=IN", snap, _tcs_score_row())
    assert resp.status_code == 200
    data = resp.json()
    assert data["stale"] is True
    assert data["quote_status"] == "quote_stale"
    assert data["current_price"] is None
    assert data["change_pct"] is None
    assert data["price_as_of"] == snap["cached_at"]


def test_in_card_last_updated_is_data_time(client):
    resp = _get(client, "/stocks/TCS?market=IN", _tcs_snap(_fresh_ts()), _tcs_score_row())
    assert resp.status_code == 200
    assert resp.json()["last_updated"] == SCORE_COMPUTED_AT


@pytest.mark.parametrize("age", ["fresh", "stale"])
def test_in_card_and_meta_agree(client, age):
    snap = _tcs_snap(_fresh_ts() if age == "fresh" else _stale_ts())
    row = _tcs_score_row()
    card = _get(client, "/stocks/TCS?market=IN", snap, row).json()
    meta = _get(client, "/stocks/TCS/meta?market=IN", snap, row).json()
    for field in ("name", "current_price", "market_cap", "pe_ttm", "stale"):
        assert card[field] == meta[field], field
    assert card["name"] == "Tata Consultancy Services Limited"
    assert card["market_cap"] == 8918585573376
    assert card["pe_ttm"] == 17.4

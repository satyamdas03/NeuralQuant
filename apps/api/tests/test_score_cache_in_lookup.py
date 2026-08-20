"""Regression test for score_cache IN ticker lookup (Bucket 1).

score_cache stores IN tickers with the .NS suffix (e.g. TCS.NS) but callers
like stocks.py and live_price.py often pass the bare ticker (TCS). read_one
must resolve both forms.
"""
from nq_api.cache import score_cache


def _make_supabase_rest(rows):
    """Return a fake _supabase_rest that filters on ticker eq."""
    def fake_rest(table, method="GET", query=None, body=None, extra_headers=None):
        if method != "GET" or table != "score_cache":
            return None
        wanted = query.get("ticker", "").replace("eq.", "")
        cutoff = query.get("computed_at", "").replace("gte.", "")
        for row in rows:
            if row["ticker"] == wanted:
                # Fake freshness by returning the row regardless of cutoff.
                return [row]
        return []
    return fake_rest


def test_read_one_finds_suffixed_in_row_with_bare_input(monkeypatch):
    rows = [
        {"ticker": "TCS.NS", "market": "IN", "composite_score": 6.5, "current_price": 3500.0,
         "long_name": "Tata Consultancy Services", "computed_at": "2026-08-18T00:00:00+00:00"},
    ]
    monkeypatch.setattr(score_cache, "_supabase_rest", _make_supabase_rest(rows))
    found = score_cache.read_one("TCS", "IN", max_age_seconds=86400)
    assert found is not None
    assert found["ticker"] == "TCS.NS"
    assert found["long_name"] == "Tata Consultancy Services"


def test_read_one_passthrough_for_us(monkeypatch):
    rows = [
        {"ticker": "AAPL", "market": "US", "composite_score": 7.0, "current_price": 180.0,
         "long_name": "Apple Inc.", "computed_at": "2026-08-18T00:00:00+00:00"},
    ]
    monkeypatch.setattr(score_cache, "_supabase_rest", _make_supabase_rest(rows))
    found = score_cache.read_one("AAPL", "US", max_age_seconds=86400)
    assert found is not None
    assert found["ticker"] == "AAPL"


def test_read_one_returns_none_when_no_match(monkeypatch):
    monkeypatch.setattr(score_cache, "_supabase_rest", _make_supabase_rest([]))
    assert score_cache.read_one("FAKE", "IN", max_age_seconds=86400) is None

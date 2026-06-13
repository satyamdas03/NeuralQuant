import time
from nq_api.services import live_price


class _FakeOBB:
    def __init__(self, quote, enabled=True):
        self._quote = quote
        self.enabled = enabled
    def get_quote(self, symbol, provider="yfinance"):
        return self._quote


def test_openbb_tier_hits_first(monkeypatch):
    live_price._CACHE.clear()
    monkeypatch.setattr(live_price, "get_openbb_client", lambda: _FakeOBB({"last_price": 205.2}))
    price, source = live_price.get_live_price("NVDA", "US")
    assert price == 205.2
    assert source == "openbb"


def test_falls_through_to_snapshot(monkeypatch):
    live_price._CACHE.clear()
    monkeypatch.setattr(live_price, "get_openbb_client", lambda: _FakeOBB(None))
    monkeypatch.setattr(live_price, "read_snapshot", lambda t, m: {"price": 3500.0})
    price, source = live_price.get_live_price("TCS", "IN")
    assert price == 3500.0
    assert source == "stock_snapshot"


def test_all_miss_returns_none(monkeypatch):
    live_price._CACHE.clear()
    monkeypatch.setattr(live_price, "get_openbb_client", lambda: _FakeOBB(None))
    monkeypatch.setattr(live_price, "read_snapshot", lambda t, m: None)
    monkeypatch.setattr(live_price, "_score_cache_price", lambda t, m: None)
    price, source = live_price.get_live_price("ZZZZ", "US")
    assert price is None
    assert source is None


def test_cache_returns_same_within_ttl(monkeypatch):
    live_price._CACHE.clear()
    calls = {"n": 0}
    def _obb():
        calls["n"] += 1
        return _FakeOBB({"last_price": 100.0})
    monkeypatch.setattr(live_price, "get_openbb_client", _obb)
    live_price.get_live_price("AAA", "US")
    live_price.get_live_price("AAA", "US")
    assert calls["n"] == 1  # second call served from cache

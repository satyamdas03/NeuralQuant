from nq_api.services import portfolio


def test_snapshot_price_returns_price(monkeypatch):
    monkeypatch.setattr(
        portfolio, "read_snapshot",
        lambda ticker, market: {"ticker": ticker, "market": market, "price": 3500.0},
    )
    assert portfolio._snapshot_price("TCS", "IN") == 3500.0


def test_snapshot_price_none_when_missing(monkeypatch):
    monkeypatch.setattr(portfolio, "read_snapshot", lambda ticker, market: None)
    assert portfolio._snapshot_price("TCS", "IN") is None


def test_snapshot_price_none_when_price_zero(monkeypatch):
    monkeypatch.setattr(
        portfolio, "read_snapshot",
        lambda ticker, market: {"price": 0},
    )
    assert portfolio._snapshot_price("TCS", "IN") is None

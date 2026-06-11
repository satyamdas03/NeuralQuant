import pandas as pd
from unittest.mock import patch

from nq_data.price import yf_guard


def test_normalize_in_adds_ns():
    assert yf_guard.normalize_ticker("TCS", "IN") == "TCS.NS"
    assert yf_guard.normalize_ticker("TCS.NS", "IN") == "TCS.NS"  # idempotent


def test_normalize_us_never_suffixed():
    assert yf_guard.normalize_ticker("AAPL", "US") == "AAPL"
    assert yf_guard.normalize_ticker("TCS.NS", "US") == "TCS"


def test_normalize_bse():
    assert yf_guard.normalize_ticker("RELIANCE", "IN_BSE") == "RELIANCE.BO"


def test_bare_ticker_strips_both():
    assert yf_guard.bare_ticker("RELIANCE.NS") == "RELIANCE"
    assert yf_guard.bare_ticker("RELIANCE.BO") == "RELIANCE"
    assert yf_guard.bare_ticker("aapl") == "AAPL"


def test_multiindex_flatten():
    df = pd.DataFrame({("Close", "AAPL"): [1.0], ("Open", "AAPL"): [0.9]})
    flat = yf_guard.flatten_columns(df)
    assert list(flat.columns) == ["Close", "Open"]


def test_flat_columns_untouched():
    df = pd.DataFrame({"Close": [1.0]})
    assert list(yf_guard.flatten_columns(df).columns) == ["Close"]


def test_render_guard_returns_none(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    assert yf_guard.download("AAPL", "US") is None


def test_retry_then_none_on_persistent_401(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setattr(yf_guard.time, "sleep", lambda s: None)
    with patch("yfinance.download", side_effect=Exception("401 Invalid Crumb")):
        assert yf_guard.download("AAPL", "US") is None


def test_nonretryable_fails_fast(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    calls = []

    def boom(*a, **k):
        calls.append(1)
        raise ValueError("schema mismatch")

    with patch("yfinance.download", side_effect=boom):
        assert yf_guard.download("AAPL", "US") is None
    assert len(calls) == 1

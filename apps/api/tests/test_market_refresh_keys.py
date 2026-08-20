"""Regression tests for market_refresh ticker-key normalization (Bucket 1).

After snapshot_cache started storing IN tickers bare, _fetch_yf_batch and
_fetch_openbb_batch must also key their result dicts by bare ticker so that
_build_snapshot_rows can merge them. These tests do not hit any network APIs.
"""
from unittest.mock import MagicMock, patch
import pandas as pd

from nq_api.jobs.market_refresh import _bare, _build_snapshot_rows


def test_bare_strips_india_suffixes():
    assert _bare("RELIANCE.NS") == "RELIANCE"
    assert _bare("TCS.BO") == "TCS"
    assert _bare("AAPL") == "AAPL"


def test_build_snapshot_rows_prefers_fmp_then_yf_bare_keys():
    """FMP and yfinance results are keyed by bare ticker; merge must use them."""
    tickers_meta = [
        {"ticker": "RELIANCE.NS", "market": "IN", "sector": "Energy", "sub_sector": "Oil",
         "qtr_beta": 1.1, "yr_beta": 1.2, "pe_ratio": 18.5, "long_name": "Reliance Industries"},
        {"ticker": "AAPL", "market": "US", "sector": "Technology", "sub_sector": "Hardware",
         "qtr_beta": 1.0, "yr_beta": 1.1, "pe_ratio": 28.0, "long_name": "Apple Inc."},
    ]
    fmp_data = {
        "AAPL": {"price": 175.0, "change_pct": 1.2, "volume": 50_000_000,
                 "market_cap": 2_700_000_000_000, "year_high": 180.0, "year_low": 160.0,
                 "name": "Apple Inc."},
    }
    yf_data = {
        "RELIANCE": {"price": 2450.0, "change_pct": 0.85, "volume": 1_200_000,
                     "market_cap": 1_600_000_000_000, "year_high": 2600.0, "year_low": 2200.0,
                     "name": "Reliance Industries Limited", "sector": "Energy", "industry": "Oil & Gas"},
    }

    rows = _build_snapshot_rows(tickers_meta, fmp_data, yf_data)
    rows_by_ticker = {r["ticker"]: r for r in rows}

    # IN row came from yfinance (bare-keyed) even though the meta ticker is suffixed.
    rel = rows_by_ticker["RELIANCE.NS"]
    assert rel["price"] == 2450.0
    assert rel["change_pct"] == 0.85
    assert rel["company_name"] == "Reliance Industries Limited"
    assert rel["source"] == "yfinance"

    # US row came from FMP (bare-keyed).
    aapl = rows_by_ticker["AAPL"]
    assert aapl["price"] == 175.0
    assert aapl["change_pct"] == 1.2
    assert aapl["source"] == "fmp"


def test_fetch_yf_batch_keys_by_bare_ticker(monkeypatch):
    """_fetch_yf_batch must return {bare_ticker: ...} even when input is suffixed."""
    from nq_api.jobs.market_refresh import _fetch_yf_batch

    fake_hist = pd.DataFrame({
        "Close": [2400.0, 2450.0],
    }, index=pd.to_datetime(["2026-08-17", "2026-08-18"]))

    # yfinance and _get_yf_session are imported locally inside _fetch_yf_batch,
    # so patch their source modules. Also stub Ticker.info to avoid network calls.
    fake_ticker = MagicMock()
    fake_ticker.info = {}
    with patch("yfinance.download", return_value=fake_hist):
        with patch("yfinance.Ticker", return_value=fake_ticker):
            with patch("nq_api.data_builder._get_yf_session", return_value=None):
                results = _fetch_yf_batch(["RELIANCE.NS"], "IN")

    assert "RELIANCE" in results
    assert results["RELIANCE"]["price"] == 2450.0
    assert results["RELIANCE"]["change_pct"] == round((2450.0 - 2400.0) / 2400.0 * 100, 2)


def test_fetch_openbb_batch_keys_by_bare_ticker(monkeypatch):
    """_fetch_openbb_batch must return {bare_ticker: ...} even when input is suffixed."""
    from nq_api.jobs.market_refresh import _fetch_openbb_batch

    fake_obb = MagicMock()
    fake_obb.enabled = True
    fake_obb.get_quote.return_value = {
        "last_price": 2450.0,
        "prev_close": 2400.0,
        "volume": 1_000_000,
        "market_cap": 1.6e12,
        "year_high": 2600.0,
        "year_low": 2200.0,
        "name": "Reliance Industries",
        "sector": "Energy",
        "industry": "Oil & Gas",
    }

    # get_openbb_client and _obb_symbol are imported locally inside _fetch_openbb_batch.
    with patch("nq_data.openbb.get_openbb_client", return_value=fake_obb):
        with patch("nq_data.openbb._obb_symbol", side_effect=lambda t, m: t):
            results = _fetch_openbb_batch(["RELIANCE.NS"], "IN")

    assert "RELIANCE" in results
    assert results["RELIANCE"]["price"] == 2450.0

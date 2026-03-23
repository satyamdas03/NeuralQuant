import pytest
from datetime import date
from nq_data.store import DataStore
from nq_data.models import OHLCVBar, FundamentalSnapshot, MacroSnapshot

def test_store_ohlcv_round_trip(tmp_store):
    bar = OHLCVBar(ticker="AAPL", market="US", date=date(2025, 1, 2),
                   open=180.0, high=185.0, low=179.0, close=182.0, volume=1e7)
    tmp_store.upsert_ohlcv([bar])
    result = tmp_store.get_ohlcv("AAPL", "US", date(2025, 1, 1), date(2025, 1, 3))
    assert len(result) == 1
    assert result[0].close == 182.0

def test_store_deduplicates_ohlcv(tmp_store):
    bar = OHLCVBar(ticker="AAPL", market="US", date=date(2025, 1, 2),
                   open=180.0, high=185.0, low=179.0, close=182.0, volume=1e7)
    tmp_store.upsert_ohlcv([bar, bar])  # Insert twice
    result = tmp_store.get_ohlcv("AAPL", "US", date(2025, 1, 1), date(2025, 1, 3))
    assert len(result) == 1  # Deduplication works

def test_store_macro_round_trip(tmp_store):
    snap = MacroSnapshot(as_of_date=date(2025, 1, 2), vix=18.5, yield_10y=4.2,
                         yield_2y=4.8, yield_spread_2y10y=-0.6, hy_spread_oas=350.0,
                         ism_pmi=52.3, cpi_yoy=3.1, fed_funds_rate=5.25, spx_vs_200ma=5.0)
    tmp_store.upsert_macro(snap)
    result = tmp_store.get_macro(date(2025, 1, 1), date(2025, 1, 3))
    assert len(result) == 1
    assert result[0].vix == 18.5
    assert result[0].yield_spread_2y10y == -0.6

def test_store_macro_deduplicates(tmp_store):
    snap = MacroSnapshot(as_of_date=date(2025, 1, 2), vix=18.5)
    snap2 = MacroSnapshot(as_of_date=date(2025, 1, 2), vix=20.0)  # Same date, updated vix
    tmp_store.upsert_macro(snap)
    tmp_store.upsert_macro(snap2)
    result = tmp_store.get_macro(date(2025, 1, 1), date(2025, 1, 3))
    assert len(result) == 1
    assert result[0].vix == 20.0

def test_store_fundamentals_round_trip(tmp_store):
    snap = FundamentalSnapshot(ticker="AAPL", market="US", as_of_date=date(2025, 1, 2),
                               pe_ttm=28.5, pb=45.2, roe=0.87)
    tmp_store.upsert_fundamentals(snap)
    result = tmp_store.get_fundamentals("AAPL", "US", date(2025, 1, 1), date(2025, 1, 3))
    assert len(result) == 1
    assert result[0].pe_ttm == 28.5
    assert result[0].roe == 0.87

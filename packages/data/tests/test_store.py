import pytest
import tempfile
from pathlib import Path
from datetime import date
from nq_data.store import DataStore
from nq_data.models import OHLCVBar

@pytest.fixture
def tmp_store(tmp_path):
    return DataStore(db_path=str(tmp_path / "test.duckdb"))

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

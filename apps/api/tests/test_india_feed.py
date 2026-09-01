"""Regression tests for the GCP India price feeder (Bucket 1).

Tests do not hit yfinance or Supabase — they verify that the feeder only
writes rows with valid prices and skips null/overwrite rows.
"""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

# Load infra/gcp/india_feed.py as a standalone module (it is not part of a package).
def _find_feed_path() -> Path:
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        candidate = parent / "infra" / "gcp" / "india_feed.py"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Could not locate infra/gcp/india_feed.py")


_FEED_PATH = _find_feed_path()
_spec = importlib.util.spec_from_file_location("india_feed", _FEED_PATH)
india_feed = importlib.util.module_from_spec(_spec)
# The script adds its own source trees to sys.path on import.
_spec.loader.exec_module(india_feed)


def test_run_feed_skips_rows_without_price(monkeypatch):
    """Rows with no yfinance price must NOT be upserted."""
    monkeypatch.setattr(
        india_feed, "load_in_tickers",
        lambda: [
            {"ticker": "TCS.NS", "market": "IN", "sector": "IT", "sub_sector": "Services",
             "qtr_beta": 0.8, "yr_beta": 0.9, "pe_ratio": 25.0},
            {"ticker": "FAKE.NS", "market": "IN", "sector": "Unknown", "sub_sector": "Unknown",
             "qtr_beta": None, "yr_beta": None, "pe_ratio": None},
        ]
    )
    monkeypatch.setattr(
        india_feed, "fetch_yf_prices",
        lambda _tickers: {"TCS": {"price": 3500.0, "change_pct": 1.2}}
    )

    written_rows = []
    def fake_write_snapshot(rows):
        written_rows.extend(rows)
        return len(rows)
    monkeypatch.setattr(india_feed, "write_snapshot", fake_write_snapshot)

    summary = india_feed.run_feed()

    assert summary["success"] is True
    assert summary["yf_hits"] == 1
    assert summary["snapshot_rows_written"] == 1
    assert summary["skipped_null_price"] == 1
    assert [r["ticker"] for r in written_rows] == ["TCS.NS"]
    assert written_rows[0]["price"] == 3500.0


def test_build_snapshot_rows_uses_bare_keys():
    meta = [{"ticker": "RELIANCE.NS", "market": "IN", "sector": "Energy", "sub_sector": "Oil",
             "qtr_beta": 1.1, "yr_beta": 1.2, "pe_ratio": 18.5}]
    yf_data = {"RELIANCE": {"price": 2450.0, "change_pct": 0.85, "volume": 12345,
                            "year_high": 2600.0, "year_low": 2200.0}}
    rows = india_feed.build_snapshot_rows(meta, yf_data, info_data={}, existing={})
    assert len(rows) == 1
    assert rows[0]["ticker"] == "RELIANCE.NS"
    assert rows[0]["price"] == 2450.0
    assert rows[0]["change_pct"] == 0.85
    assert rows[0]["volume"] == 12345
    assert rows[0]["week_52_high"] == 2600.0
    assert rows[0]["week_52_low"] == 2200.0

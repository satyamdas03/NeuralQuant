"""Regression: market_refresh must not overwrite snapshots with price-less rows.

Observed 2026-10-18 02:43 UTC on Render: FMP was not configured, so every US
row came back empty ("fmp_hits": 0). market_refresh still wrote 446 rows with
price null and a fresh cached_at and reported success, and the score rebuild
then served current_price 0.0 for every US stock.
"""

from unittest.mock import patch

from nq_api.jobs import market_refresh as mr

_META = [
    {"ticker": "AAPL", "market": "US", "long_name": "Apple Inc."},
    {"ticker": "MSFT", "market": "US", "long_name": "Microsoft Corporation"},
]


def _run(fmp_results):
    written = {}

    def fake_write(rows):
        written["rows"] = list(rows)
        return len(rows)

    with patch.object(mr, "_load_tickers_from_supabase", return_value=list(_META)), \
         patch.object(mr, "_fetch_fmp_batch", return_value=fmp_results), \
         patch.object(mr.time, "sleep", lambda s: None), \
         patch("nq_api.cache.snapshot_cache.write_snapshot", side_effect=fake_write) as ws:
        result = mr.run_market_refresh(market_filter="US")
    return result, written.get("rows"), ws


def test_fmp_down_writes_nothing_and_reports_failure():
    result, rows, ws = _run({})
    assert ws.call_count == 0
    assert rows is None
    assert result["success"] is False
    assert result["snapshot_rows_written"] == 0
    assert result["rows_skipped_no_price"] == 2


def test_partial_fmp_writes_only_priced_rows():
    result, rows, ws = _run({"AAPL": {"price": 250.0, "change_pct": 1.2, "name": "Apple Inc."}})
    assert [r["ticker"] for r in rows] == ["AAPL"]
    assert rows[0]["price"] == 250.0
    assert result["success"] is True
    assert result["rows_skipped_no_price"] == 1

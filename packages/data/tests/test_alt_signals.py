import pytest
from unittest.mock import patch
from datetime import date
from nq_data.alt_signals.edgar_form4 import Form4Connector, compute_insider_cluster_score

def test_form4_returns_insider_events():
    connector = Form4Connector()
    with patch.object(connector, "_fetch_raw", return_value=[{
        "ticker": "NVDA",
        "officer_title": "CEO",
        "transaction_date": date(2025, 1, 10),
        "shares": 5000,
        "price_per_share": 480.0,
        "is_purchase": True,
    }]):
        events = connector.get_insider_events("NVDA", date(2025, 1, 1), date(2025, 1, 15))
    assert len(events) == 1
    assert events[0]["is_purchase"] is True
    assert events[0]["ticker"] == "NVDA"

def test_form4_cluster_signal():
    """A cluster of insider buys should return positive signal score."""
    events = [
        {"is_purchase": True, "shares": 5000, "price_per_share": 480.0,
         "transaction_date": date(2025, 1, i), "officer_title": "CEO"}
        for i in range(1, 4)
    ]
    score = compute_insider_cluster_score(events, lookback_days=90)
    assert score > 0.5  # Strong cluster buy signal

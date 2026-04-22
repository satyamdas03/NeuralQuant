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


def test_form4_empty_events_neutral():
    """No insider activity must be neutral (0.5), not a bottom score."""
    assert compute_insider_cluster_score([]) == 0.5


def test_form4_heavy_selling_below_midpoint():
    events = [
        {"is_purchase": False, "officer_title": "CEO"},
        {"is_purchase": False, "officer_title": "CFO"},
    ]
    score = compute_insider_cluster_score(events)
    assert 0.0 <= score < 0.5


def test_form4_parses_xml_fixture():
    """End-to-end parse of a minimal Form 4 XML payload."""
    import unittest.mock as um
    xml = b"""<?xml version='1.0'?>
    <ownershipDocument>
      <reportingOwner>
        <reportingOwnerRelationship>
          <isDirector>0</isDirector>
          <isOfficer>1</isOfficer>
          <officerTitle>Chief Executive Officer</officerTitle>
        </reportingOwnerRelationship>
      </reportingOwner>
      <nonDerivativeTable>
        <nonDerivativeTransaction>
          <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
          <transactionAmounts>
            <transactionShares><value>1000</value></transactionShares>
            <transactionPricePerShare><value>100.25</value></transactionPricePerShare>
            <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
          </transactionAmounts>
        </nonDerivativeTransaction>
      </nonDerivativeTable>
    </ownershipDocument>
    """
    connector = Form4Connector()
    fake_resp = um.MagicMock(status_code=200, content=xml)
    with um.patch(
        "nq_data.alt_signals.edgar_form4.requests.get", return_value=fake_resp
    ), um.patch(
        "nq_data.alt_signals.edgar_form4.broker.acquire",
        return_value=um.MagicMock(__enter__=lambda s: None, __exit__=lambda *a: None),
    ):
        result = connector._parse_filing_xml("https://example/primary.xml")

    assert result is not None
    assert result["is_purchase"] is True
    assert result["shares"] == 1000
    assert abs(result["price"] - 100.25) < 1e-6
    assert "CHIEF EXECUTIVE" in result["officer_title"].upper() or \
           "CEO" in result["officer_title"].upper() or \
           result["officer_title"] == "Chief Executive Officer"

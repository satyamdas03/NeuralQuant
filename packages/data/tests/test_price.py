import pytest
from unittest.mock import patch, MagicMock
from datetime import date
import pandas as pd
from nq_data.price.yfinance_connector import YFinanceConnector
from nq_data.price.nse_bhavcopy import NSEBhavCopyConnector
from nq_data.models import OHLCVBar

def make_mock_yf_df():
    idx = pd.DatetimeIndex([pd.Timestamp("2025-01-02")], name="Date")
    return pd.DataFrame({
        "Open": [180.0], "High": [185.0], "Low": [179.0],
        "Close": [182.0], "Volume": [1e7], "Adj Close": [182.0]
    }, index=idx)

def test_yfinance_connector_returns_ohlcv_bars():
    connector = YFinanceConnector()
    with patch("yfinance.download", return_value=make_mock_yf_df()):
        bars = connector.fetch("AAPL", "US", date(2025,1,1), date(2025,1,3))
    assert len(bars) == 1
    assert bars[0].ticker == "AAPL"
    assert bars[0].market == "US"
    assert bars[0].close == 182.0

def test_yfinance_appends_ns_suffix_for_india():
    connector = YFinanceConnector()
    with patch("yfinance.download", return_value=make_mock_yf_df()) as mock_dl:
        connector.fetch("TRENT", "IN", date(2025,1,1), date(2025,1,3))
        call_args = mock_dl.call_args[0][0]
        assert call_args == "TRENT.NS"

def test_nse_bhavcopy_parses_csv(tmp_path):
    """NSEBhavCopyConnector should parse Bhavcopy CSV format."""
    csv_content = "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY,DELIV_QTY\n"
    csv_content += "TRENT,EQ,6200.0,6350.0,6180.0,6300.0,500000,250000\n"
    csv_file = tmp_path / "bhavcopy.csv"
    csv_file.write_text(csv_content)
    connector = NSEBhavCopyConnector()
    bars = connector.parse_bhavcopy(str(csv_file), date(2025, 1, 2))
    assert len(bars) == 1
    assert bars[0].ticker == "TRENT"
    assert bars[0].delivery_pct == pytest.approx(50.0, abs=0.1)

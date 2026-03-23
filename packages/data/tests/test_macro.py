import pytest
from unittest.mock import patch, MagicMock
from datetime import date
import pandas as pd
from nq_data.macro.fred_connector import FREDConnector
from nq_data.models import MacroSnapshot

def test_fred_connector_builds_snapshot():
    mock_series = {
        "VIXCLS": pd.Series([15.2], index=pd.DatetimeIndex([pd.Timestamp("2025-01-02")])),
        "DGS10": pd.Series([4.3], index=pd.DatetimeIndex([pd.Timestamp("2025-01-02")])),
        "DGS2": pd.Series([4.7], index=pd.DatetimeIndex([pd.Timestamp("2025-01-02")])),
        "BAMLH0A0HYM2": pd.Series([3.2], index=pd.DatetimeIndex([pd.Timestamp("2025-01-02")])),
        "MANEMP": pd.Series([49.5], index=pd.DatetimeIndex([pd.Timestamp("2025-01-02")])),
        "FEDFUNDS": pd.Series([5.25], index=pd.DatetimeIndex([pd.Timestamp("2025-01-02")])),
        "CPIAUCSL": pd.Series([312.0], index=pd.DatetimeIndex([pd.Timestamp("2025-01-02")])),
    }
    # Connector must be created inside the patch block so __init__ receives the mock Fred class
    with patch("nq_data.macro.fred_connector.Fred") as MockFred:
        instance = MockFred.return_value
        instance.get_series.side_effect = lambda sid, **kw: mock_series.get(sid, pd.Series())
        connector = FREDConnector(api_key="test_key")
        snapshot = connector.get_snapshot(date(2025, 1, 2))
    assert snapshot.vix == pytest.approx(15.2)
    assert snapshot.yield_10y == pytest.approx(4.3)
    assert snapshot.yield_spread_2y10y == pytest.approx(-0.4, abs=0.01)  # 4.3 - 4.7

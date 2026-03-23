import os
from datetime import date, timedelta
from fredapi import Fred
from ..models import MacroSnapshot
from ..broker import broker

SERIES = {
    "vix":             "VIXCLS",
    "yield_10y":       "DGS10",
    "yield_2y":        "DGS2",
    "hy_spread_oas":   "BAMLH0A0HYM2",
    "ism_pmi":         "MANEMP",  # ISM Manufacturing PMI
    "fed_funds_rate":  "FEDFUNDS",
    "cpi":             "CPIAUCSL",
}

class FREDConnector:
    def __init__(self, api_key: str | None = None):
        key = api_key or os.environ["FRED_API_KEY"]
        self._fred = Fred(api_key=key)

    def _fetch(self, series_id: str, as_of: date) -> float | None:
        start = (as_of - timedelta(days=10)).isoformat()
        with broker.acquire("fred"):
            s = self._fred.get_series(series_id, observation_start=start,
                                      observation_end=as_of.isoformat())
        if s.empty:
            return None
        return float(s.dropna().iloc[-1])

    def get_snapshot(self, as_of: date) -> MacroSnapshot:
        vals = {k: self._fetch(sid, as_of) for k, sid in SERIES.items()}
        y10 = vals.get("yield_10y")
        y2 = vals.get("yield_2y")
        spread = (y10 - y2) if (y10 is not None and y2 is not None) else None
        return MacroSnapshot(
            as_of_date=as_of,
            vix=vals.get("vix"),
            yield_10y=y10,
            yield_2y=y2,
            yield_spread_2y10y=spread,
            hy_spread_oas=vals.get("hy_spread_oas"),
            ism_pmi=vals.get("ism_pmi"),
            cpi_yoy=vals.get("cpi"),  # Will compute YoY % in signal engine
            fed_funds_rate=vals.get("fed_funds_rate"),
        )

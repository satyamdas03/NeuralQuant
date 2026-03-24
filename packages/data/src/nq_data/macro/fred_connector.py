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
    "ism_pmi":         "NAPMPMI",  # ISM Manufacturing PMI Composite (post-2002 series)
    "fed_funds_rate":  "FEDFUNDS",
}

class FREDConnector:
    def __init__(self, api_key: str | None = None):
        key = api_key or os.environ.get("FRED_API_KEY")
        if not key:
            raise ValueError(
                "FRED_API_KEY environment variable not set. "
                "Register for a free key at https://fred.stlouisfed.org/docs/api/api_key.html"
            )
        self._fred = Fred(api_key=key)

    def _fetch(self, series_id: str, as_of: date) -> float | None:
        """Fetch a single FRED series; returns None on any error (retired/missing series, etc.)."""
        try:
            # Monthly series may need a wider lookback window (up to 60 days for PMI, fed funds)
            start = (as_of - timedelta(days=60)).isoformat()
            with broker.acquire("fred"):
                s = self._fred.get_series(series_id, observation_start=start,
                                          observation_end=as_of.isoformat())
            if s is None or s.empty:
                return None
            dropped = s.dropna()
            if dropped.empty:
                return None
            return float(dropped.iloc[-1])
        except Exception:
            return None  # Series retired, not found, or network error — caller uses fallback

    def get_snapshot(self, as_of: date) -> MacroSnapshot:
        vals = {k: self._fetch(sid, as_of) for k, sid in SERIES.items()}
        y10 = vals.get("yield_10y")
        y2 = vals.get("yield_2y")
        spread = (y10 - y2) if (y10 is not None and y2 is not None) else None

        # Compute CPI YoY % by fetching current and year-ago CPI level
        cpi_now = self._fetch("CPIAUCSL", as_of)
        one_year_ago = as_of.replace(year=as_of.year - 1)
        cpi_year_ago = self._fetch("CPIAUCSL", one_year_ago)
        cpi_yoy_pct = (
            (cpi_now / cpi_year_ago - 1) * 100
            if (cpi_now is not None and cpi_year_ago is not None and cpi_year_ago != 0)
            else None
        )

        return MacroSnapshot(
            as_of_date=as_of,
            vix=vals.get("vix"),
            yield_10y=y10,
            yield_2y=y2,
            yield_spread_2y10y=spread,
            hy_spread_oas=vals.get("hy_spread_oas"),
            ism_pmi=vals.get("ism_pmi"),
            cpi_yoy=cpi_yoy_pct,
            fed_funds_rate=vals.get("fed_funds_rate"),
        )

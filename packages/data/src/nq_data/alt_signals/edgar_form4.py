"""
SEC EDGAR Form 4 insider trading signals.
Free API: https://efts.sec.gov/LATEST/search-index
Rate limit: 10 req/sec — handled by DataBroker.
Note: _fetch_raw returns filing metadata only. Full XML parsing of individual
filings (for shares, price, is_purchase) is deferred to Phase 2.
"""
import warnings
import requests
from datetime import date, timedelta
from ..broker import broker

EDGAR_HEADERS = {
    "User-Agent": "NeuralQuant research@neuralquant.ai",
    "Accept-Encoding": "gzip, deflate",
}
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"

class Form4Connector:
    def _fetch_raw(self, ticker: str, start: date, end: date) -> list[dict]:
        """Fetch Form 4 filings for a ticker from EDGAR full-text search.

        Returns filing metadata. Full XML parsing for transaction details
        (shares, price, is_purchase) is stub — Phase 2 will complete this.
        """
        params = {
            "q": f'"{ticker}"',
            "forms": "4",
            "dateRange": "custom",
            "startdt": start.isoformat(),
            "enddt": end.isoformat(),
        }
        with broker.acquire("edgar"):
            resp = requests.get(EDGAR_SEARCH, params=params, headers=EDGAR_HEADERS, timeout=15)
        if resp.status_code != 200:
            return []
        hits = resp.json().get("hits", {}).get("hits", [])
        results = []
        for hit in hits:
            src = hit.get("_source", {})
            results.append({
                "ticker": ticker,
                "file_date": src.get("file_date"),
                "period": src.get("period_of_report"),
                "form_type": src.get("form_type"),
            })
        return results

    def get_insider_events(self, ticker: str, start: date, end: date) -> list[dict]:
        """Return parsed insider transaction events. Override _fetch_raw in tests."""
        events = self._fetch_raw(ticker, start, end)
        # Warn if live data is returned without parsed transaction fields
        # (Phase 2 will add full XML parsing)
        if events and "is_purchase" not in events[0]:
            warnings.warn(
                f"Form4Connector._fetch_raw returned filing metadata only — "
                f"is_purchase/shares/price fields are not available until Phase 2 XML parsing. "
                f"compute_insider_cluster_score will return 0.0 for live data.",
                UserWarning,
                stacklevel=2,
            )
        return events


def compute_insider_cluster_score(events: list[dict], lookback_days: int = 90) -> float:
    """
    Score from 0.0 to 1.0 based on insider buying cluster.
    Algorithm:
    - Count net purchases (buys - sells) weighted by officer seniority
    - Normalize by lookback period
    - CEO/President = 3x weight, CFO/COO = 2x, Director = 1x
    """
    WEIGHTS = {"CEO": 3, "PRESIDENT": 3, "CFO": 2, "COO": 2, "CTO": 2}

    net_weighted = 0.0
    for e in events:
        title = (e.get("officer_title") or "").upper()
        weight = next((v for k, v in WEIGHTS.items() if k in title), 1)
        if e.get("is_purchase"):
            net_weighted += weight
        else:
            net_weighted -= weight * 0.5  # Sells count less (often routine diversification)

    # Normalize: 5 weighted buys = strong signal (1.0)
    return min(1.0, max(0.0, net_weighted / 5.0))

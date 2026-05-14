"""NSE India quote data — 52-week high/low from unofficial NSE API.
Free, no API key. Follows nse_bhavcopy.py pattern (NSE_HEADERS, broker.acquire)."""

import logging
import requests
from ..broker import broker

log = logging.getLogger(__name__)

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.nseindia.com",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
}

QUOTE_URL = "https://www.nseindia.com/api/quote-equity?symbol={symbol}"
_shared_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _shared_session
    if _shared_session is None:
        _shared_session = requests.Session()
        _shared_session.headers.update(NSE_HEADERS)
        try:
            _shared_session.get("https://www.nseindia.com", timeout=15)
        except Exception:
            pass
    return _shared_session


def fetch_nse_quote(symbol: str) -> dict | None:
    """Fetch quote data for a single NSE symbol. Returns {week52_high, week52_low, ...} or None."""
    clean = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
    try:
        session = _get_session()
        with broker.acquire("nse"):
            resp = session.get(QUOTE_URL.format(symbol=clean), timeout=15)
        if resp.status_code != 200:
            return None
        data = resp.json()
        price_info = data.get("priceInfo", {})
        return {
            "week52_high": price_info.get("week52High"),
            "week52_low": price_info.get("week52Low"),
            "previous_close": price_info.get("previousClose"),
            "open": price_info.get("open"),
            "last_price": price_info.get("lastPrice"),
            "vwap": price_info.get("vwap"),
        }
    except Exception as exc:
        log.debug("NSE quote failed for %s: %s", symbol, exc)
        return None


def fetch_nse_52w(symbol: str) -> dict | None:
    """Fetch just 52-week high/low for a symbol. Lighter-weight."""
    quote = fetch_nse_quote(symbol)
    if not quote:
        return None
    result = {}
    if quote.get("week52_high"):
        result["week52_high"] = quote["week52_high"]
    if quote.get("week52_low"):
        result["week52_low"] = quote["week52_low"]
    return result or None

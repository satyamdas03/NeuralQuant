import logging
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
from ..models import OHLCVBar
from ..broker import broker

log = logging.getLogger(__name__)

SUFFIX = {"IN": ".NS", "IN_BSE": ".BO"}


def _is_crumb_error(exc: Exception) -> bool:
    """Detect yfinance 'Invalid Crumb' or 401 auth errors."""
    msg = str(exc).lower()
    return "crumb" in msg or "401" in msg or "unauthorized" in msg


def _clear_yf_crumb_cache():
    """Clear yfinance internal crumb/cookie cache so next call re-authenticates.

    In yfinance >= 0.2.x the crumb is stored per-session; resetting the
    shared session forces a fresh authentication handshake with Yahoo.
    """
    try:
        # yfinance stores crumb/cookie in utils module — clear them
        import yfinance.utils as yf_utils
        if hasattr(yf_utils, "_CRUMB"):
            yf_utils._CRUMB = None
        if hasattr(yf_utils, "_COOKIE"):
            yf_utils._COOKIE = None
        # Also clear the cached session if present in the data_builder module
        try:
            from nq_api.data_builder import _get_yf_session, _yf_session
            import nq_api.data_builder as _db
            if hasattr(_db, "_yf_session") and _db._yf_session not in (None, False):
                # Create a fresh curl_cffi session
                try:
                    from curl_cffi.requests import Session as CurlSession
                    _db._yf_session = CurlSession(impersonate="chrome", timeout=30)
                    log.info("Reset yfinance session after crumb error")
                except ImportError:
                    _db._yf_session = None
        except ImportError:
            pass  # data_builder not available (standalone data package)
    except Exception:
        log.debug("Failed to clear yfinance crumb cache: %s", exc_info=True)


class YFinanceConnector:
    def fetch(self, ticker: str, market: str,
              start: date, end: date) -> list[OHLCVBar]:
        """Fetch daily OHLCV bars. Market: 'US' | 'IN' | 'IN_BSE'

        Retries once on yfinance 'Invalid Crumb' auth errors.
        """
        yf_ticker = ticker + SUFFIX.get(market, "")
        for attempt in range(2):
            try:
                with broker.acquire("yfinance"):
                    df = yf.download(
                        yf_ticker,
                        start=start.isoformat(),
                        end=(end + timedelta(days=1)).isoformat(),
                        progress=False,
                        auto_adjust=False,
                    )
                break  # success — exit retry loop
            except Exception as exc:
                if _is_crumb_error(exc) and attempt == 0:
                    log.warning("yfinance crumb error for %s, clearing cache and retrying", yf_ticker)
                    _clear_yf_crumb_cache()
                    continue
                raise

        if df.empty:
            return []
        # Flatten MultiIndex columns if present (newer yfinance versions)
        if isinstance(df.columns, pd.MultiIndex):
            # Find which level has the price fields (Open, High, Low, Close, Volume)
            price_fields = {"Open", "High", "Low", "Close", "Volume", "Adj Close"}
            if any(c in price_fields for c in df.columns.get_level_values(0)):
                df.columns = df.columns.get_level_values(0)  # level 0 = price fields
            else:
                df.columns = df.columns.get_level_values(1)  # level 1 = price fields
        df = df.reset_index()
        # Normalize Date column name
        if "Datetime" in df.columns:
            df = df.rename(columns={"Datetime": "Date"})
        bars = []
        store_market = "IN" if market == "IN_BSE" else market
        for _, row in df.iterrows():
            bars.append(OHLCVBar(
                ticker=ticker,
                market=store_market,
                date=row["Date"].date() if hasattr(row["Date"], "date") else row["Date"],
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row["Volume"]),
                adjusted_close=float(row.get("Adj Close", row["Close"])),
            ))
        return bars

    def fetch_batch(self, tickers: list[str], market: str,
                    start: date, end: date) -> list[OHLCVBar]:
        """Batch fetch for efficiency — yfinance supports multi-ticker download.

        Retries once on yfinance 'Invalid Crumb' auth errors.
        """
        suffixed = [t + SUFFIX.get(market, "") for t in tickers]
        for attempt in range(2):
            try:
                with broker.acquire("yfinance"):
                    df = yf.download(
                        " ".join(suffixed),
                        start=start.isoformat(),
                        end=(end + timedelta(days=1)).isoformat(),
                        progress=False,
                        auto_adjust=False,
                        group_by="ticker",
                    )
                break  # success — exit retry loop
            except Exception as exc:
                if _is_crumb_error(exc) and attempt == 0:
                    log.warning("yfinance crumb error in batch fetch, clearing cache and retrying")
                    _clear_yf_crumb_cache()
                    continue
                raise

        if df.empty:
            return []

        # Handle MultiIndex columns from newer yfinance
        if isinstance(df.columns, pd.MultiIndex):
            # group_by="ticker" puts ticker as level 0, field as level 1
            # or field as level 0, ticker as level 1 depending on version
            # Try to detect and normalize so level 0 = tickers
            levels = df.columns.get_level_values(0).unique().tolist()
            if any(t in levels for t in suffixed):
                # level 0 = tickers (expected format)
                pass
            else:
                # swap levels so tickers are at level 0
                df.columns = df.columns.swaplevel()

        store_market = "IN" if market == "IN_BSE" else market
        bars = []
        for orig_ticker, suffixed_ticker in zip(tickers, suffixed):
            try:
                sub = df[suffixed_ticker].dropna(subset=["Close"])
            except KeyError:
                continue
            for ts, row in sub.iterrows():
                bars.append(OHLCVBar(
                    ticker=orig_ticker, market=store_market,
                    date=ts.date(),
                    open=float(row["Open"]), high=float(row["High"]),
                    low=float(row["Low"]), close=float(row["Close"]),
                    volume=float(row["Volume"]),
                    adjusted_close=float(row.get("Adj Close", row["Close"])),
                ))
        return bars
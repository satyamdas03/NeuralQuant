"""yf_guard — the preferred gateway for ad-hoc yfinance calls in this codebase.

Encodes every yfinance failure mode discovered across Sessions 8-81:
  - 401/403 on cloud IPs (curl_cffi browser impersonation)      [bug 47]
  - "Invalid Crumb" 401 (retry condition)                        [bug 114]
  - MultiIndex column crashes                                    [bug 38]
  - Missing .NS suffix for India                                 [bugs 50, 124, 126]
  - Infinite hangs (hard timeout)                                [bugs 19, 90]
  - Render cloud-IP blocks (skip entirely, caller falls to FMP)  [bug 90]

All guarded functions return None on failure — callers MUST treat None as
"fall to FMP / cache", which the existing 6-7-tier fallback chains already do.

NOTE: OHLCV batch history goes through YFinanceConnector (yfinance_connector.py),
which shares the same crumb-retry + MultiIndex handling. This module is for
quote/info/news/spot-download paths scattered through the API layer.
"""
from __future__ import annotations

import functools
import logging
import os
import time

import pandas as pd

log = logging.getLogger(__name__)

YF_TIMEOUT_S = 20
YF_RETRIES = 3
_RETRYABLE = ("401", "403", "crumb", "Invalid Crumb", "Unauthorized", "timed out")


def _on_render() -> bool:
    # Matches the codebase convention: Render sets RENDER to a non-empty value.
    return bool(os.environ.get("RENDER"))


def _session():
    """curl_cffi browser-impersonation session (bug 47). None if unavailable."""
    try:
        from curl_cffi import requests as curl_requests
        return curl_requests.Session(impersonate="chrome", timeout=30)
    except ImportError:
        return None


def normalize_ticker(ticker: str, market: str) -> str:
    """Bare ticker in, exchange-suffixed ticker out. NEVER suffix US. (bugs 1, 50, 124, 126)"""
    t = ticker.upper().strip().removesuffix(".NS").removesuffix(".BO")
    if market.upper() in ("IN", "IN_NSE"):
        return f"{t}.NS"
    if market.upper() == "IN_BSE":
        return f"{t}.BO"
    return t


def bare_ticker(ticker: str) -> str:
    """Suffixed ticker in, bare cache-key out. Cache keys are ALWAYS bare. (bug 126)"""
    return ticker.upper().strip().removesuffix(".NS").removesuffix(".BO")


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance MultiIndex columns -> flat (bug 38)."""
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def _retryable(err: Exception) -> bool:
    msg = str(err)
    return any(k.lower() in msg.lower() for k in _RETRYABLE)


def guarded(fn):
    """Decorator: retry/backoff + Render guard + never-raise discipline."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if _on_render():
            log.info("yf_guard skip on Render: %s", fn.__name__)
            return None  # caller MUST handle None -> FMP/cache fallback
        last = None
        for attempt in range(1, YF_RETRIES + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as e:  # noqa: BLE001 — gateway boundary
                last = e
                if not _retryable(e) or attempt == YF_RETRIES:
                    log.warning("yf_guard fail %s attempt=%d err=%s",
                                fn.__name__, attempt, str(e)[:200])
                    return None
                time.sleep(0.8 * attempt)
        log.warning("yf_guard exhausted %s err=%s", fn.__name__, str(last)[:200])
        return None
    return wrapper


@guarded
def download(ticker: str, market: str = "US", period: str = "5d",
             interval: str = "1d") -> pd.DataFrame | None:
    import yfinance as yf
    t = normalize_ticker(ticker, market)
    df = yf.download(t, period=period, interval=interval, progress=False,
                     timeout=YF_TIMEOUT_S, session=_session())
    if df is None or df.empty:
        return None
    return flatten_columns(df)


@guarded
def info(ticker: str, market: str = "US") -> dict | None:
    import yfinance as yf
    t = normalize_ticker(ticker, market)
    return yf.Ticker(t, session=_session()).info


@guarded
def news(ticker: str, market: str = "US") -> list | None:
    import yfinance as yf
    t = normalize_ticker(ticker, market)
    items = yf.Ticker(t, session=_session()).news or []
    out = []
    for it in items:  # bug 39: headline under title OR content.title
        title = it.get("title") or (it.get("content") or {}).get("title")
        if title:
            out.append({**it, "title": title})
    return out

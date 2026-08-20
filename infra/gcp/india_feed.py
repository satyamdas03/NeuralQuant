#!/usr/bin/env python3
"""Autonomous India price feeder for the GCP Always-Free VM.

Fetches Indian (NSE) stock prices via yfinance from the GCP VM's IP
(Yahoo does not block GCP the way it blocks Render), then upserts the
results into Supabase public.stock_snapshot.

Intended to run as a cron job on the same GCP e2-micro VM that hosts
Hermes. The cron window should cover Indian market hours:
    09:15–15:30 IST  ==  03:45–10:00 UTC  (Mon–Fri)

This script is DELIBERATELY SELF-CONTAINED. It does not import from the
nq_api / nq_data workspace packages, so the VM only needs a lightweight
venv with yfinance, curl_cffi, pandas, httpx and python-dotenv.

Example crontab (every 15 min during market window):
    */15 3-10 * * 1-5 /opt/neuralquant/venv/bin/python /opt/neuralquant/infra/gcp/india_feed.py >> /var/log/india_feed.log 2>&1
"""
from __future__ import annotations

import logging
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# Load environment from repo .env
# -----------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parents[2]  # infra/gcp/india_feed.py -> project root
_ENV_PATH = _PROJECT_ROOT / "apps" / "api" / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH, override=True)

import yfinance as yf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("india_feed")

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
_YF_CHUNK_SIZE = 50          # yfinance batch download handles ~50 symbols well
_CHUNK_DELAY_S = 2           # small pause between yf.download chunks
_MAX_AGE_MINUTES = 35        # stale threshold (matches market_refresh)


# -----------------------------------------------------------------------------
# Minimal yfinance session helpers (copied from data_builder to stay self-contained)
# -----------------------------------------------------------------------------
_yf_session = None


def _get_yf_session():
    """Return a curl_cffi session for yfinance."""
    global _yf_session
    if _yf_session is None:
        try:
            from curl_cffi.requests import Session as CurlSession
            _yf_session = CurlSession(impersonate="chrome", timeout=30)
            log.info("Using curl_cffi session for yfinance (impersonate=chrome, timeout=30s)")
        except ImportError:
            log.error("curl_cffi is NOT installed — yfinance calls will fail on cloud IPs!")
            _yf_session = False
    return _yf_session if _yf_session else None


def _reset_yf_session():
    """Reset the shared yfinance session after an Invalid Crumb auth error."""
    global _yf_session
    old = _yf_session
    _yf_session = None
    if old and old is not False:
        try:
            old.close()
        except Exception:
            pass
    try:
        import yfinance.utils as yf_utils
        if hasattr(yf_utils, "_CRUMB"):
            yf_utils._CRUMB = None
        if hasattr(yf_utils, "_COOKIE"):
            yf_utils._COOKIE = None
    except Exception:
        pass
    log.info("Reset yfinance session after crumb/auth error")


def _is_yf_crumb_error(exc: Exception) -> bool:
    """Detect yfinance 'Invalid Crumb' or 401 auth errors."""
    msg = str(exc).lower()
    return "crumb" in msg or "401" in msg or "unauthorized" in msg


# -----------------------------------------------------------------------------
# Minimal Supabase REST helpers (copied to stay self-contained)
# -----------------------------------------------------------------------------
_env_loaded = False


def _load_env():
    global _env_loaded
    if _env_loaded:
        return
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH, override=True)
    _env_loaded = True


def _is_nonfinite(v) -> bool:
    try:
        import pandas as pd
        if pd.isna(v) and v is not None and v is not False:
            return True
    except Exception:
        pass
    if isinstance(v, float):
        return math.isnan(v) or math.isinf(v)
    if hasattr(v, "__float__") and not isinstance(v, (str, int, bool, type(None))):
        try:
            fv = float(v)
            return math.isnan(fv) or math.isinf(fv)
        except (TypeError, ValueError):
            pass
    return False


def _sanitize_floats(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if _is_nonfinite(v):
            out[k] = None
        elif isinstance(v, dict):
            out[k] = _sanitize_floats(v)
        elif isinstance(v, list):
            out[k] = [
                _sanitize_floats(i) if isinstance(i, dict)
                else (None if _is_nonfinite(i) else i)
                for i in v
            ]
        elif hasattr(v, "__float__") and not isinstance(v, (str, int, bool, type(None))):
            try:
                fv = float(v)
                out[k] = None if _is_nonfinite(fv) else fv
            except (TypeError, ValueError):
                out[k] = v
        else:
            out[k] = v
    return out


def _supabase_rest(
    table: str,
    method: str = "GET",
    query: dict | None = None,
    body: list[dict[str, Any]] | dict[str, Any] | None = None,
) -> list[dict[str, Any]] | dict[str, Any] | None:
    """Direct REST call to Supabase PostgREST API."""
    _load_env()
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        log.error("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set")
        return None

    endpoint = f"{url}/rest/v1/{table}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    if body is not None:
        if isinstance(body, list):
            body = [_sanitize_floats(item) if isinstance(item, dict) else item for item in body]
        elif isinstance(body, dict):
            body = _sanitize_floats(body)

    try:
        _timeout = 30 if method == "POST" else 10
        with httpx.Client(timeout=_timeout) as client:
            if method == "GET":
                r = client.get(endpoint, params=query or {}, headers=headers)
            elif method == "POST":
                upsert_headers = {**headers, "Prefer": "resolution=merge-duplicates,return=representation"}
                r = client.post(endpoint, json=body, headers=upsert_headers)
            elif method == "PATCH":
                r = client.patch(endpoint, json=body, params=query or {}, headers=headers)
            elif method == "DELETE":
                r = client.delete(endpoint, params=query or {}, headers=headers)
            else:
                return None
            r.raise_for_status()
            return r.json() if r.content else None
    except Exception as e:
        log.warning("Supabase REST call failed for table=%s: %s", table, e)
        return None


# -----------------------------------------------------------------------------
# Minimal snapshot upsert (copied to stay self-contained)
# -----------------------------------------------------------------------------
_known_snapshot_columns: set[str] | None = None


def _get_snapshot_columns() -> set[str]:
    global _known_snapshot_columns
    if _known_snapshot_columns is not None:
        return _known_snapshot_columns
    data = _supabase_rest("stock_snapshot", "GET", {"select": "*", "limit": "1"})
    if isinstance(data, list) and data:
        _known_snapshot_columns = set(data[0].keys())
    else:
        _known_snapshot_columns = {
            "ticker", "market", "price", "change_pct", "volume", "market_cap",
            "pe_ttm", "eps", "beta", "pb_ratio", "week_52_high", "week_52_low",
            "earnings_date", "analyst_target", "recommendation", "rsi_14d",
            "macd_signal", "insider_score", "news_sentiment", "sector",
            "sub_sector", "company_name", "currency", "cached_at", "stale", "source",
        }
    return _known_snapshot_columns


def _normalize_snapshot_ticker(ticker: str, market: str) -> str:
    t = ticker.upper()
    if market == "IN":
        t = t.replace(".NS", "").replace(".BO", "")
    return t


def write_snapshot(rows: list[dict[str, Any]]) -> int:
    """Batch upsert rows into stock_snapshot keyed on (ticker, market)."""
    if not rows:
        return 0
    known = _get_snapshot_columns()
    now_iso = datetime.now(timezone.utc).isoformat()
    for r in rows:
        r.setdefault("cached_at", now_iso)
        if r.get("market") == "IN" and "ticker" in r:
            r["ticker"] = _normalize_snapshot_ticker(r["ticker"], "IN")
    filtered = [_sanitize_floats({k: v for k, v in r.items() if k in known}) for r in rows]
    result = _supabase_rest("stock_snapshot", method="POST", body=filtered)
    return len(rows) if result is not None else 0


# -----------------------------------------------------------------------------
# Feeder logic
# -----------------------------------------------------------------------------
def _yf_sym(ticker: str) -> str:
    """Append .NS for NSE tickers that don't already have an exchange suffix."""
    t = ticker.strip().upper()
    if "." not in t:
        return t + ".NS"
    return t


def _bare(ticker: str) -> str:
    return ticker.upper().replace(".NS", "").replace(".BO", "")


def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        fv = float(v)
        if math.isnan(fv) or math.isinf(fv):
            return None
        return fv
    except (TypeError, ValueError):
        return None


def _safe_int(v) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


_GARBAGE_RE = re.compile(
    r"(?:LIGHT\s*GREEN|DARK\s*GREEN|LIGHT\s*RED|DARK\s*RED|WHITE|COLOR|SCORING|"
    r"GROWTH|RETURN|VALUATION|RISK|RATIOS|SOURCE|FUTURE|BENCHMARK|HIERARCH|"
    r"MATCHED|WORST|BEST|CHEAPEST|EXPENSIVE|SAFEST|RISKIEST|SWEET\s*SPOT|"
    r"UNCOLORED|LOSS.MAKING|NETPROFIT|EXCLUDED|YFINANCE|YOY|TTM|QOQ|"
    r"PERIOD|MARKET\s*CAP|REVENUE|DII|FII|PB|EV/|SUM|Q\d+\(|^[A-Z]{1,2}$)",
    re.IGNORECASE,
)


def _is_valid_ticker(t: str) -> bool:
    """Conservative ticker validator (avoids Excel-legend garbage rows)."""
    t = t.strip().upper()
    if not t or len(t) > 12 or len(t) < 2:
        return False
    if _GARBAGE_RE.search(t):
        return False
    if not any(c.isalpha() for c in t):
        return False
    return True


def load_in_tickers() -> list[dict[str, Any]]:
    """Load IN tickers from quantfactor_universe."""
    data = _supabase_rest(
        "quantfactor_universe",
        method="GET",
        query={
            "select": "ticker,market,sector,sub_sector,qtr_beta,yr_beta,pe_ratio,computed_at",
            "market": "eq.IN",
            "limit": "10000",
        },
    )
    if not isinstance(data, list):
        log.error("Failed to load IN tickers from quantfactor_universe")
        return []
    filtered = [r for r in data if _is_valid_ticker(str(r.get("ticker", "")))]
    log.info("Loaded %s IN tickers from quantfactor_universe (raw=%s)", len(filtered), len(data))
    return filtered


def fetch_yf_prices(tickers: list[str]) -> dict[str, dict]:
    """Batch-fetch live prices for IN tickers via yfinance.

    Returns {bare_ticker: {price, change_pct}}.
    """
    if not tickers:
        return {}

    results: dict[str, dict] = {}
    session = _get_yf_session()
    syms = [_yf_sym(t) for t in tickers]
    bare_list = [_bare(t) for t in tickers]

    for i in range(0, len(syms), _YF_CHUNK_SIZE):
        chunk_syms = syms[i : i + _YF_CHUNK_SIZE]
        chunk_bare = bare_list[i : i + _YF_CHUNK_SIZE]
        for attempt in range(2):
            try:
                hist = yf.download(
                    chunk_syms,
                    period="5d",
                    progress=False,
                    auto_adjust=True,
                    threads=False,
                    session=session,
                )
                if hist is not None and not hist.empty and "Close" in hist.columns:
                    close = hist["Close"]
                    for bare_t, sym in zip(chunk_bare, chunk_syms):
                        try:
                            if len(chunk_syms) > 1 and sym in close.columns:
                                vals = close[sym].dropna()
                            elif len(chunk_syms) == 1:
                                vals = close.dropna()
                            else:
                                vals = None
                            if vals is not None and len(vals) >= 2:
                                price = float(vals.iloc[-1])
                                prev = float(vals.iloc[-2])
                                entry = results.setdefault(bare_t, {})
                                entry["price"] = price
                                entry["change_pct"] = round((price - prev) / prev * 100, 2)
                        except Exception:
                            pass
                break  # success
            except Exception as e:
                if _is_yf_crumb_error(e) and attempt == 0:
                    log.warning("yf.download crumb error, resetting session and retrying")
                    _reset_yf_session()
                    session = _get_yf_session()
                    continue
                log.warning("yf.download chunk failed: %s", e)
                break
        time.sleep(_CHUNK_DELAY_S)

    return results


def build_snapshot_rows(
    tickers_meta: list[dict[str, Any]],
    yf_data: dict[str, dict],
) -> list[dict[str, Any]]:
    """Merge yfinance results with static quantfactor metadata."""
    rows = []
    now_iso = datetime.now(timezone.utc).isoformat()
    for meta in tickers_meta:
        t = meta["ticker"]
        bare = _bare(t)
        yf = yf_data.get(bare, {})

        price = yf.get("price")
        change_pct = yf.get("change_pct")
        beta = meta.get("qtr_beta") or meta.get("yr_beta")
        if beta is None:
            beta = yf.get("beta")

        row = {
            "ticker": t,
            "market": "IN",
            "price": _safe_float(price),
            "change_pct": _safe_float(change_pct),
            "volume": _safe_int(yf.get("volume")),
            "market_cap": _safe_float(yf.get("market_cap")),
            "pe_ttm": _safe_float(meta.get("pe_ratio")),
            "eps": None,
            "beta": _safe_float(beta),
            "pb_ratio": None,
            "week_52_high": _safe_float(yf.get("year_high")),
            "week_52_low": _safe_float(yf.get("year_low")),
            "earnings_date": None,
            "analyst_target": None,
            "recommendation": None,
            "rsi_14d": None,
            "macd_signal": None,
            "insider_score": None,
            "news_sentiment": None,
            "sector": meta.get("sector") or yf.get("sector"),
            "sub_sector": meta.get("sub_sector") or yf.get("industry"),
            "company_name": yf.get("name") or bare,
            "currency": "INR",
            "cached_at": now_iso,
            "stale": False,
            "source": "gcp_yfinance",
        }
        rows.append(row)
    return rows


def run_feed(limit: int | None = None) -> dict[str, Any]:
    """Main entrypoint: fetch IN prices and write to Supabase."""
    start = time.monotonic()
    tickers_meta = load_in_tickers()
    if not tickers_meta:
        return {"success": False, "error": "No IN tickers loaded", "elapsed_seconds": 0}
    if limit:
        tickers_meta = tickers_meta[:limit]
        log.info("Test mode: limiting to first %s tickers", limit)

    log.info("Fetching yfinance prices for %s IN tickers", len(tickers_meta))
    yf_data = fetch_yf_prices([m["ticker"] for m in tickers_meta])
    log.info("yfinance returned prices for %s / %s tickers", len(yf_data), len(tickers_meta))

    rows = build_snapshot_rows(tickers_meta, yf_data)
    # Never overwrite existing good prices with nulls/zeros — only upsert rows
    # that actually got a price from yfinance.
    rows_with_price = [r for r in rows if r.get("price") and float(r["price"]) > 0]
    skipped = len(rows) - len(rows_with_price)
    if skipped:
        log.info("Skipping %s rows without a valid price", skipped)
    written = write_snapshot(rows_with_price) if rows_with_price else 0

    elapsed = round(time.monotonic() - start, 1)
    summary = {
        "success": True,
        "total_tickers": len(tickers_meta),
        "yf_hits": len(yf_data),
        "snapshot_rows_written": written,
        "skipped_null_price": skipped,
        "elapsed_seconds": elapsed,
    }
    log.info("India feed complete: %s", summary)
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="India price feeder")
    parser.add_argument("--limit", type=int, default=None, help="Only refresh first N tickers (for testing)")
    args = parser.parse_args()

    result = run_feed(limit=args.limit)
    sys.exit(0 if result.get("success") else 1)

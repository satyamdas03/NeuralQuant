#!/usr/bin/env python3
"""Autonomous India price feeder for the GCP Always-Free VM.

Fetches Indian (NSE) stock prices via yfinance from the GCP VM's IP
(Yahoo does not block GCP the way it blocks Render), then upserts the
results into Supabase public.stock_snapshot.

Intended to run as a cron job on the same GCP e2-micro VM that hosts
Hermes. The cron window should cover Indian market hours:
    09:15–15:30 IST  ==  03:45–10:00 UTC  (Mon–Fri)

Example crontab (every 15 min during market window):
    */15 3-10 * * 1-5 /opt/neuralquant/venv/bin/python /opt/neuralquant/infra/gcp/india_feed.py >> /var/log/india_feed.log 2>&1
"""
from __future__ import annotations

import logging
import math
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

# -----------------------------------------------------------------------------
# Paths: when run from /opt/neuralquant/infra/gcp/india_feed.py, project root
# is /opt/neuralquant. Add the source trees so we can reuse existing helpers.
# -----------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# infra/gcp/india_feed.py -> project root is two levels up
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "../.."))
for _src in (f"{_PROJECT_ROOT}/apps/api/src", f"{_PROJECT_ROOT}/packages/data/src"):
    if _src not in sys.path:
        sys.path.insert(0, _src)

from dotenv import load_dotenv

# Load apps/api/.env (Supabase credentials live there).
_ENV_PATH = os.path.join(_PROJECT_ROOT, "apps", "api", ".env")
if os.path.exists(_ENV_PATH):
    load_dotenv(_ENV_PATH, override=True)

import yfinance as yf
from nq_api.cache.quantfactor_cache import _supabase_rest
from nq_api.cache.snapshot_cache import write_snapshot
from nq_api.data_builder import _get_yf_session
from nq_data.ticker_validation import is_valid_ticker

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
    filtered = [r for r in data if is_valid_ticker(str(r.get("ticker", "")))]
    log.info("Loaded %s IN tickers from quantfactor_universe (raw=%s)", len(filtered), len(data))
    return filtered


def _is_yf_crumb_error(exc: Exception) -> bool:
    """Detect yfinance 'Invalid Crumb' or 401 auth errors."""
    msg = str(exc).lower()
    return "crumb" in msg or "401" in msg or "unauthorized" in msg


def fetch_yf_prices(tickers: list[str]) -> dict[str, dict]:
    """Batch-fetch live prices for IN tickers via yfinance.

    Returns {bare_ticker: {price, change_pct}}. We intentionally avoid
    individual Ticker.info calls — they are slow (500 tickers × 1s throttle
    ≈ 8 min) and not needed for the core goal of populating price/change_pct.
    Name/sector come from quantfactor_universe metadata.
    """
    if not tickers:
        return {}

    from nq_api.data_builder import _reset_yf_session

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

"""Market refresh job: batch-fetches live prices + fundamentals for ALL stocks
every 30 minutes and upserts into stock_snapshot.

Runs as a GitHub Actions cron (free tier) or can be triggered manually via
POST /cron/market-refresh.

Data flow:
    1. Read ticker list from quantfactor_universe (primary) or anjali_enrichment (fallback)
    2. FMP batch quotes (50 per call) → price, change_pct, volume, market_cap, 52w
    3. For IN stocks where FMP fails → yfinance fallback
    4. Beta / sector / sub_sector → from quantfactor_universe (static, no API call)
    5. Compute P/E explicitly when FMP batch PE is null
    6. Upsert everything into stock_snapshot
"""
from __future__ import annotations

import logging
import math
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

# Add project root to path for standalone GHA execution
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_BATCH_SIZE = 50          # FMP batch quote limit
_FMP_RATE_LIMIT = 300     # calls/min (conservative; Premium = 750)
_YF_BATCH_SIZE = 20       # yfinance concurrent thread limit for IN fallback
_MAX_AGE_MINUTES = 35     # stale threshold


def _yf_sym(ticker: str, market: str) -> str:
    if market == "IN" and "." not in ticker:
        return ticker + ".NS"
    return ticker


def _bare(ticker: str) -> str:
    return ticker.upper().replace(".NS", "").replace(".BO", "")


# ---------------------------------------------------------------------------
# Ticker list loaders
# ---------------------------------------------------------------------------

def _load_tickers_from_supabase() -> list[dict]:
    """Load all tickers from quantfactor_universe (primary) or anjali_enrichment (fallback)."""
    from nq_api.cache.quantfactor_cache import _supabase_rest

    # Primary: quantfactor_universe
    data = _supabase_rest(
        "quantfactor_universe",
        method="GET",
        query={"select": "ticker,market,sector,sub_sector,qtr_beta,yr_beta,pe_ratio,computed_at", "limit": "10000"},
    )
    if isinstance(data, list) and data:
        import re
        _GARBAGE = re.compile(
            r"(?:LIGHT\s*GREEN|DARK\s*GREEN|LIGHT\s*RED|DARK\s*RED|WHITE|COLOR|SCORING|"
            r"GROWTH|RETURN|VALUATION|RISK|RATIOS|SOURCE|FUTURE|BENCHMARK|HIERARCH|"
            r"MATCHED|WORST|BEST|CHEAPEST|EXPENSIVE|SAFEST|RISKIEST|SWEET\s*SPOT|"
            r"UNCOLORED|LOSS.MAKING|NETPROFIT|EXCLUDED|YFINANCE|YOY|TTM|QOQ|"
            r"PERIOD|MARKET\s*CAP|REVENUE|DII|FII|PB|EV/|SUM|Q\d+\(|^[A-Z]{1,2}$|^NAN$|^NONE$)",
            re.IGNORECASE,
        )
        filtered = []
        for r in data:
            t = str(r.get("ticker", "")).strip().upper()
            if not t or len(t) > 8 or len(t) < 2:
                continue
            if _GARBAGE.search(t):
                continue
            if not any(c.isalpha() for c in t):
                continue
            filtered.append(r)
        log.info("Loaded %s tickers from quantfactor_universe (filtered from %s)", len(filtered), len(data))
        return filtered

    # Fallback 1: anjali_enrichment (during migration period)
    data = _supabase_rest(
        "anjali_enrichment",
        method="GET",
        query={"select": "ticker,market,sector,sub_sector,qtr_beta,yr_beta,pe_ratio,computed_at", "limit": "10000"},
    )
    if isinstance(data, list) and data:
        log.info("Loaded %s tickers from anjali_enrichment (fallback)", len(data))
        return data

    # Fallback 2: hardcoded US + Indian universes
    log.warning("No quantfactor_universe or anjali_enrichment data — using hardcoded fallback")
    from nq_api.universe import UNIVERSE_BY_MARKET
    rows = []
    for market, tickers in UNIVERSE_BY_MARKET.items():
        for t in tickers:
            rows.append({"ticker": t, "market": market, "sector": None, "sub_sector": None,
                         "qtr_beta": None, "yr_beta": None, "pe_ratio": None, "computed_at": None})
    return rows


# ---------------------------------------------------------------------------
# FMP batch fetch
# ---------------------------------------------------------------------------

def _fetch_fmp_batch(tickers: list[str], market: str) -> dict[str, dict]:
    """Fetch FMP batch quotes for a list of tickers. Returns {symbol: quote_dict}."""
    from nq_data.fmp import get_fmp_client
    fmp = get_fmp_client()
    if not fmp._enabled:
        log.warning("FMP not enabled — skipping batch fetch")
        return {}

    # Resolve symbols (add .NS for Indian stocks)
    syms = [_yf_sym(t, market) for t in tickers]

    try:
        result = fmp.get_batch_quotes(syms)
        if not result:
            return {}
        # Map back from resolved symbol to bare ticker
        mapped = {}
        for raw_sym, quote in result.items():
            bare = _bare(raw_sym)
            mapped[bare] = quote
        return mapped
    except Exception as e:
        log.warning("FMP batch fetch failed: %s", e)
        return {}


# ---------------------------------------------------------------------------
# yfinance fallback (IN stocks only)
# ---------------------------------------------------------------------------

def _fetch_yf_batch(tickers: list[str], market: str) -> dict[str, dict]:
    """Fetch yfinance data for tickers that FMP missed.

    Uses yf.download for batch price data (1 call) then individual .info
    for fundamentals with 2s throttle to avoid rate limiting.
    """
    import yfinance as yf
    from nq_api.data_builder import _get_yf_session

    results = {}
    session = _get_yf_session()

    # Phase 1: Batch download for prices (1 API call for all tickers)
    syms = [_yf_sym(t, market) for t in tickers]
    try:
        hist = yf.download(syms, period="5d", progress=False, auto_adjust=True,
                          threads=False, session=session)
        if hist is not None and not hist.empty and "Close" in hist.columns:
            close = hist["Close"]
            for t, sym in zip(tickers, syms):
                try:
                    col = sym if len(syms) > 1 else "Close"
                    if len(syms) > 1 and sym in close.columns:
                        vals = close[sym].dropna()
                    elif len(syms) == 1:
                        vals = close.dropna()
                    else:
                        vals = None
                    if vals is not None and len(vals) >= 2:
                        price = float(vals.iloc[-1])
                        prev = float(vals.iloc[-2])
                        results.setdefault(t, {})["price"] = price
                        results.setdefault(t, {})["change_pct"] = round((price - prev) / prev * 100, 2)
                except Exception:
                    pass
    except Exception as e:
        log.debug("yf.download batch failed: %s", e)

    # Phase 2: Individual .info calls for fundamentals (throttled 2s each)
    for t in tickers:
        sym = _yf_sym(t, market)
        try:
            info = yf.Ticker(sym, session=session).info or {}
            entry = results.setdefault(t, {})
            # Only fill fields not already set by download
            if not entry.get("price"):
                entry["price"] = info.get("currentPrice") or info.get("regularMarketPrice")
            if not entry.get("change_pct"):
                prev = info.get("previousClose")
                price = entry.get("price")
                if price is not None and prev and prev > 0:
                    entry["change_pct"] = round((price - prev) / prev * 100, 2)
            entry["volume"] = info.get("volume") or info.get("regularMarketVolume")
            entry["market_cap"] = info.get("marketCap")
            entry["pe"] = info.get("trailingPE")
            entry["year_high"] = info.get("fiftyTwoWeekHigh")
            entry["year_low"] = info.get("fiftyTwoWeekLow")
            entry["name"] = info.get("longName") or info.get("shortName") or t
            entry["sector"] = info.get("sector")
            entry["industry"] = info.get("industry")
            entry["beta"] = info.get("beta")
        except Exception as e:
            log.debug("yfinance .info failed for %s: %s", t, e)
        time.sleep(2)  # Rate limit throttle: 2s between calls
    return results


# ---------------------------------------------------------------------------
# Build snapshot rows
# ---------------------------------------------------------------------------

def _build_snapshot_rows(
    tickers_meta: list[dict],
    fmp_data: dict[str, dict],
    yf_data: dict[str, dict],
) -> list[dict[str, Any]]:
    """Merge FMP + yfinance + static quantfactor data into snapshot rows."""
    rows = []
    for meta in tickers_meta:
        t = meta["ticker"]
        m = meta["market"]
        fmp = fmp_data.get(t, {})
        yf = yf_data.get(t, {})

        # Price priority: FMP → yfinance → None
        price = fmp.get("price") if fmp.get("price") is not None else yf.get("price")
        change_pct = fmp.get("change_pct") if fmp.get("change_pct") is not None else yf.get("change_pct")
        volume = fmp.get("volume") if fmp.get("volume") is not None else yf.get("volume")
        market_cap = fmp.get("market_cap") if fmp.get("market_cap") is not None else yf.get("market_cap")

        # 52w range
        week_52_high = fmp.get("year_high") if fmp.get("year_high") is not None else yf.get("year_high")
        week_52_low = fmp.get("year_low") if fmp.get("year_low") is not None else yf.get("year_low")

        # P/E: FMP batch often null — try yfinance, then static quantfactor, then None
        pe_ttm = fmp.get("pe")
        if pe_ttm is None:
            pe_ttm = yf.get("pe")
        if pe_ttm is None:
            pe_ttm = meta.get("pe_ratio")

        # Beta: static quantfactor first, then yfinance, then FMP batch (rare)
        beta = meta.get("qtr_beta") or meta.get("yr_beta")
        if beta is None:
            beta = yf.get("beta")

        # Company name / sector
        company_name = yf.get("name") if yf else None
        sector = meta.get("sector") or (yf.get("sector") if yf else None)
        sub_sector = meta.get("sub_sector") or (yf.get("industry") if yf else None)

        # Currency
        currency = "INR" if m == "IN" else "USD"

        row = {
            "ticker": t,
            "market": m,
            "price": _safe_num(price),
            "change_pct": _safe_num(change_pct),
            "volume": _safe_int(volume),
            "market_cap": _safe_num(market_cap),
            "pe_ttm": _safe_num(pe_ttm),
            "eps": None,  # computed on-demand in meta endpoint or next refresh
            "beta": _safe_num(beta),
            "pb_ratio": None,
            "week_52_high": _safe_num(week_52_high),
            "week_52_low": _safe_num(week_52_low),
            "earnings_date": None,
            "analyst_target": None,
            "recommendation": None,
            "rsi_14d": None,
            "macd_signal": None,
            "insider_score": None,
            "news_sentiment": None,
            "sector": sector,
            "sub_sector": sub_sector,
            "company_name": company_name,
            "currency": currency,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "stale": False,
            "source": "fmp" if fmp else ("yfinance" if yf else "fallback"),
        }
        rows.append(row)
    return rows


def _safe_num(v) -> float | None:
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
        iv = int(v)
        return iv
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Main refresh logic
# ---------------------------------------------------------------------------

def run_market_refresh(market_filter: str | None = None) -> dict:
    """Run the full market refresh pipeline.

    Args:
        market_filter: If provided, only refresh this market ('US' or 'IN').
                       If None, refresh all markets.

    Returns:
        Summary dict with counts and timing.
    """
    from nq_api.cache.snapshot_cache import write_snapshot

    start = time.monotonic()
    log.info("market_refresh starting (market_filter=%s)", market_filter)

    # 1. Load ticker universe
    all_meta = _load_tickers_from_supabase()
    if market_filter:
        all_meta = [m for m in all_meta if m.get("market") == market_filter]

    if not all_meta:
        log.error("No tickers to refresh")
        return {"success": False, "error": "No tickers loaded", "elapsed_seconds": 0}

    # Group by market for symbol resolution
    by_market: dict[str, list[dict]] = {}
    for m in all_meta:
        mk = m.get("market", "US")
        by_market.setdefault(mk, []).append(m)

    # 2. Fetch FMP batch quotes per market
    fmp_results: dict[str, dict] = {}
    for mk, meta_list in by_market.items():
        tickers = [m["ticker"] for m in meta_list]
        # Batch in chunks of _BATCH_SIZE
        for i in range(0, len(tickers), _BATCH_SIZE):
            chunk = tickers[i:i + _BATCH_SIZE]
            chunk_results = _fetch_fmp_batch(chunk, mk)
            fmp_results.update(chunk_results)
            time.sleep(0.5)  # brief pause between batch calls

    # 3. Identify tickers that FMP missed entirely
    missing_by_market: dict[str, list[str]] = {}
    for mk, meta_list in by_market.items():
        missing = [m["ticker"] for m in meta_list if m["ticker"] not in fmp_results or not fmp_results[m["ticker"]]]
        if missing:
            missing_by_market[mk] = missing

    # 4. yfinance fallback for missing tickers (primarily IN stocks)
    yf_results: dict[str, dict] = {}
    for mk, missing in missing_by_market.items():
        if mk == "IN":
            log.info("yfinance fallback for %s IN tickers", len(missing))
            # Process in batches to avoid overwhelming yfinance
            for i in range(0, len(missing), _YF_BATCH_SIZE):
                chunk = missing[i:i + _YF_BATCH_SIZE]
                chunk_results = _fetch_yf_batch(chunk, mk)
                yf_results.update(chunk_results)
                time.sleep(1)
        else:
            log.warning("FMP missed %s US tickers — no fallback (yfinance unreliable on cloud)", len(missing))

    # 5. Build snapshot rows
    rows = _build_snapshot_rows(all_meta, fmp_results, yf_results)

    # 6. Upsert to Supabase
    written = write_snapshot(rows)

    elapsed = time.monotonic() - start
    summary = {
        "success": True,
        "total_tickers": len(all_meta),
        "fmp_hits": len(fmp_results),
        "yf_hits": len(yf_results),
        "snapshot_rows_written": written,
        "elapsed_seconds": round(elapsed, 1),
    }
    log.info("market_refresh complete: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Market refresh job")
    parser.add_argument("--market", type=str, default=None, help="Filter to one market (US or IN)")
    args = parser.parse_args()
    result = run_market_refresh(market_filter=args.market)
    print(result)
    sys.exit(0 if result.get("success") else 1)

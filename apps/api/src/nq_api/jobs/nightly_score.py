"""Nightly score cache builder — importable from FastAPI cron endpoint.

Reuses the same logic as scripts/nightly_score.py but structured as
importable functions rather than a CLI script.
"""
from __future__ import annotations

import logging
import math
import os
import sys
import time
from pathlib import Path

log = logging.getLogger(__name__)

# Ensure packages importable when running standalone
ROOT = Path(__file__).resolve().parents[4]
if str(ROOT / "packages" / "data" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages" / "data" / "src"))
if str(ROOT / "packages" / "signals" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages" / "signals" / "src"))
if str(ROOT / "apps" / "api" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

import pandas as pd
from nq_api.universe import UNIVERSE_FULL
from nq_api.data_builder import build_real_snapshot
from nq_api.deps import get_signal_engine
from nq_api.sector_rank import apply_sector_adjustment
from nq_api.cache import score_cache

CHUNK = 20
SLEEP_BETWEEN_CHUNKS = 1.0


def _f(v, default: float = 0.0) -> float:
    """Coerce to finite float; NaN/None/inf → default."""
    try:
        if v is None or (isinstance(v, float) and not math.isfinite(v)):
            return float(default)
        if pd.isna(v):
            return float(default)
        f = float(v)
        return f if math.isfinite(f) else float(default)
    except (TypeError, ValueError):
        return float(default)


def _run_market_from_quantfactor(market: str) -> int:
    """Build score_cache from quantfactor_universe + FMP batch quotes.
    Fast-path for Render cloud where yfinance is rate-limited.
    Uses Anjali Excel data (growth/return/valuation/risk/composite/irs_pct)
    + FMP live prices instead of expensive build_real_snapshot pipeline."""
    from nq_api.cache.quantfactor_cache import _supabase_rest as _qf_rest
    try:
        from nq_data.fmp import get_fmp_client
        fmp = get_fmp_client()
    except Exception:
        fmp = None

    # 1. Read quantfactor_universe rows for this market
    qf_rows = _qf_rest(
        "quantfactor_universe", "GET",
        {"select": "*", "market": f"eq.{market}", "limit": "500"},
    )
    if not qf_rows:
        log.warning("[%s] No quantfactor_universe rows — falling back to full pipeline", market)
        return 0

    log.info("[%s] quantfactor_universe: %d rows", market, len(qf_rows))

    # 2. Batch FMP quotes for live prices
    fmp_prices: dict[str, dict] = {}
    if fmp and fmp._enabled:
        try:
            all_syms = [r.get("ticker", "") for r in qf_rows if r.get("ticker")]
            if market == "IN":
                all_syms = [t if "." in t else f"{t}.NS" for t in all_syms]
            # Batch in chunks of 50 (FMP limit)
            for i in range(0, len(all_syms), 50):
                chunk = all_syms[i:i+50]
                batch = fmp.get_batch_quotes(chunk) or {}
                fmp_prices.update(batch)
        except Exception as exc:
            log.warning("[%s] FMP batch quotes failed: %s", market, exc)

    # 3. Build score_cache rows from quantfactor + FMP
    all_results = []
    for r in qf_rows:
        t = r.get("ticker", "")
        # FMP live price
        price = 0.0
        if fmp_prices:
            fb = (fmp_prices.get(t) or fmp_prices.get(f"{t}.NS") or fmp_prices.get(f"{t}.BO") or {})
            price = float(fb.get("price") or 0)

        # Derive composite_score from quantfactor composite (scale 0-1 → 0-10)
        qf_composite = r.get("composite")
        composite_score = float(qf_composite) * 10 if qf_composite is not None else 5.0

        # Derive percentiles from quantfactor scores (scale 0-4 → 0-1)
        def _pct(val, max_val=4.0):
            try:
                return min(1.0, max(0.0, float(val) / max_val)) if val is not None else 0.5
            except (TypeError, ValueError):
                return 0.5

        all_results.append({
            "ticker": t,
            "market": market,
            "sector": r.get("sector", "Unknown") or "Unknown",
            "composite_score": composite_score,
            "value_percentile": _pct(r.get("valuation_score")),
            "momentum_percentile": _pct(r.get("return_score")),  # return ≈ momentum
            "quality_percentile": _pct(r.get("growth_score")),  # growth ≈ quality
            "low_vol_percentile": _pct(r.get("risk_score"), 4.0),  # risk ≈ low_vol inverse
            "growth_percentile": _pct(r.get("growth_score")),
            "short_interest_percentile": 0.5,
            "current_price": price,
            "analyst_target": 0.0,
            "pe_ttm": float(r.get("pe_ttm") or 0),
            "market_cap": float(r.get("market_cap") or 0),
            "week52_high": float(r.get("week52_high") or 0),
            "week52_low": float(r.get("week52_low") or 0),
            "momentum_raw": 0.0,
            "gross_profit_margin": 0.0,
            "piotroski": 5,
            "pb_ratio": float(r.get("pb_ratio") or 0),
            "beta": float(r.get("beta") or 0),
            "realized_vol_1y": 0.0,
            "short_interest_pct": 0.0,
            "insider_cluster_score": 0.5,
            "accruals_ratio": 0.0,
            "revenue_growth_yoy": 0.0,
            "debt_equity": 0.0,
            "roe": float(r.get("roe") or 0),
            "fcf_yield": 0.0,
            "long_name": r.get("name", "") or t,
            "industry": r.get("industry", "") or "",
            "analyst_rec": r.get("analyst_rec", "") or "",
            "earnings_date": "",
            "dividend_yield": float(r.get("dividend_yield") or 0),
        })

    if not all_results:
        return 0

    # Rank within market
    all_results.sort(key=lambda r: r["composite_score"], reverse=True)
    for rank, r in enumerate(all_results, start=1):
        r["rank_score"] = rank

    written = 0
    for i in range(0, len(all_results), 100):
        batch = all_results[i:i+100]
        written += score_cache.upsert_scores(batch)
    log.info("[%s] quantfactor path: upserted %d rows", market, written)
    return written


def run_market(market: str) -> int:
    """Build scores for one market and upsert to Supabase. Returns row count."""
    # On Render: use fast path from quantfactor_universe + FMP (no yfinance)
    if os.environ.get("RENDER"):
        count = _run_market_from_quantfactor(market)
        if count > 0:
            return count
        log.warning("[%s] quantfactor fast path returned 0 — falling back to full pipeline", market)

    rows = UNIVERSE_FULL.get(market, [])
    tickers = [r["ticker"] for r in rows]
    log.info("[%s] universe size: %d", market, len(tickers))

    engine = get_signal_engine()
    all_results = []

    for i in range(0, len(tickers), CHUNK):
        batch = tickers[i : i + CHUNK]
        log.info("[%s] chunk %d: %s..%s", market, i // CHUNK + 1, batch[0], batch[-1])
        try:
            snap = build_real_snapshot(batch, market)
            df = engine.compute(snap)
            df = apply_sector_adjustment(df)
            for _, row in df.iterrows():
                all_results.append({
                    "ticker": str(row["ticker"]),
                    "market": market,
                    "sector": str(row.get("sector", "Unknown") or "Unknown"),
                    "composite_score": _f(row.get("composite_score"), 0.0),
                    "value_percentile": _f(row.get("value_percentile"), 0.5),
                    "momentum_percentile": _f(row.get("momentum_percentile"), 0.5),
                    "quality_percentile": _f(row.get("quality_percentile"), 0.5),
                    "low_vol_percentile": _f(row.get("low_vol_percentile"), 0.5),
                    "growth_percentile": _f(row.get("growth_percentile"), 0.5),
                    "short_interest_percentile": _f(row.get("short_interest_percentile"), 0.5),
                    "current_price": _f(row.get("current_price")),
                    "analyst_target": _f(row.get("analyst_target")),
                    "pe_ttm": _f(row.get("pe_ttm")),
                    "market_cap": _f(row.get("market_cap")),
                    "week52_high": _f(row.get("week52_high")),
                    "week52_low": _f(row.get("week52_low")),
                    "momentum_raw": _f(row.get("momentum_raw")),
                    "gross_profit_margin": _f(row.get("gross_profit_margin")),
                    "piotroski": _f(row.get("piotroski"), 5),
                    "pb_ratio": _f(row.get("pb_ratio")),
                    "beta": _f(row.get("beta")),
                    "realized_vol_1y": _f(row.get("realized_vol_1y")),
                    "short_interest_pct": _f(row.get("short_interest_pct")),
                    "insider_cluster_score": _f(row.get("insider_cluster_score")),
                    "accruals_ratio": _f(row.get("accruals_ratio")),
                    "revenue_growth_yoy": _f(row.get("revenue_growth_yoy")),
                    "debt_equity": _f(row.get("debt_equity")),
                    "roe": _f(row.get("roe")),
                    "fcf_yield": _f(row.get("fcf_yield")),
                    "long_name": str(row.get("long_name") or row.get("ticker", "")),
                    "industry": str(row.get("industry") or ""),
                    "analyst_rec": str(row.get("analyst_rec") or ""),
                    "earnings_date": str(row.get("earnings_date") or ""),
                    "dividend_yield": _f(row.get("dividend_yield")),
                })
        except Exception as exc:
            log.exception("[%s] chunk failed: %s", market, exc)
        time.sleep(SLEEP_BETWEEN_CHUNKS)

    # Rank within market
    all_results.sort(key=lambda r: r["composite_score"], reverse=True)
    for rank, r in enumerate(all_results, start=1):
        r["rank_score"] = rank

    written = 0
    for i in range(0, len(all_results), 100):
        batch = all_results[i : i + 100]
        written += score_cache.upsert_scores(batch)
    log.info("[%s] upserted %d rows", market, written)
    return written


def warm_stock_meta(market: str = "US") -> int:
    """Populate stock_meta table in parallel (8 workers, 15s timeout per ticker)."""
    import json as _json
    from datetime import datetime, timezone
    from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait as fut_wait
    from nq_api.cache.score_cache import _supabase_rest

    tickers = UNIVERSE_FULL.get(market, [])
    ticker_syms = [r["ticker"] if isinstance(r, dict) else str(r) for r in tickers]
    log.info("[%s] warming stock_meta for %d tickers (parallel 8 workers)", market, len(ticker_syms))

    # Skip on Render to avoid yfinance timeouts
    if os.environ.get("RENDER"):
        log.info("[%s] Skipping stock_meta warm on Render (yfinance rate-limits)", market)
        return 0

    written = 0
    for i in range(0, len(ticker_syms), 50):
        batch = ticker_syms[i : i + 50]
        ex = ThreadPoolExecutor(max_workers=8)
        try:
            fut_map = {ex.submit(_warm_one_ticker, sym, market): sym for sym in batch}
            pending = set(fut_map.keys())
            while pending:
                done, pending = fut_wait(pending, timeout=15, return_when=FIRST_COMPLETED)
                for future in done:
                    sym = fut_map[future]
                    try:
                        row = future.result(timeout=0)
                        if row:
                            _supabase_rest("stock_meta", method="PATCH", body=[row],
                                           query={"ticker": f"eq.{sym}", "market": f"eq.{market}"})
                            written += 1
                    except Exception as exc:
                        log.warning("[%s] stock_meta failed for %s: %s", market, sym, exc)
        finally:
            ex.shutdown(wait=False)

    log.info("[%s] stock_meta warm complete: %d tickers", market, written)
    return written


def _warm_one_ticker(sym: str, market: str) -> dict | None:
    """Fetch stock_meta row for a single ticker."""
    import json as _json
    from datetime import datetime, timezone
    import yfinance as yf

    yf_sym = sym + ".NS" if market == "IN" and "." not in sym else sym
    t = yf.Ticker(yf_sym)
    info = t.info or {}
    if not info:
        return None

    earnings_date = None
    try:
        cal = t.calendar
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if ed and len(ed) > 0:
                earnings_date = str(ed[0].date())
    except Exception:
        pass

    mc = info.get("marketCap")
    price_now = info.get("currentPrice") or info.get("regularMarketPrice")

    div_pct = None
    div_rate = info.get("dividendRate")
    if div_rate and price_now:
        try:
            v = float(div_rate) / float(price_now) * 100
            if 0 < v < 20:
                div_pct = round(v, 2)
        except Exception:
            pass
    if div_pct is None:
        div_raw = info.get("dividendYield")
        if div_raw:
            try:
                v = float(div_raw)
                v = v if v > 1 else v * 100
                if 0 < v < 20:
                    div_pct = round(v, 2)
            except Exception:
                pass

    return {
        "ticker": sym,
        "market": market,
        "data": _json.dumps({
            "ticker": sym,
            "name": info.get("longName") or info.get("shortName") or sym,
            "market_cap": mc,
            "market_cap_fmt": _fmt_mcap(float(mc), market) if mc else None,
            "pe_ttm": round(float(info["trailingPE"]), 1) if info.get("trailingPE") else None,
            "pb_ratio": round(float(info["priceToBook"]), 2) if info.get("priceToBook") else None,
            "beta": round(float(info["beta"]), 2) if info.get("beta") else None,
            "week_52_high": info.get("fiftyTwoWeekHigh"),
            "week_52_low": info.get("fiftyTwoWeekLow"),
            "earnings_date": earnings_date,
            "analyst_target": info.get("targetMeanPrice"),
            "analyst_recommendation": info.get("recommendationKey"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "dividend_yield": div_pct,
            "current_price": price_now,
        }),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def _fmt_mcap(mc: float, market: str) -> str:
    if mc >= 1e12:
        return f"${mc/1e12:.1f}T"
    if mc >= 1e9:
        return f"${mc/1e9:.1f}B"
    if mc >= 1e6:
        return f"${mc/1e6:.1f}M"
    return f"${mc:,.0f}"
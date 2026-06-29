"""Nightly score cache builder — importable from FastAPI cron endpoint.

Reuses the same logic as scripts/nightly_score.py but structured as
importable functions rather than a CLI script.
"""
from __future__ import annotations

import logging
import math
import os
import re
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

    # 0. Delete stale/garbage rows from score_cache for this market before rebuilding
    try:
        _qf_rest("score_cache", method="DELETE", query={"market": f"eq.{market}"})
        log.info("[%s] Deleted existing score_cache rows before rebuild", market)
    except Exception as e:
        log.warning("[%s] Failed to delete existing score_cache rows: %s", market, e)

    # 1. Read quantfactor_universe rows for this market
    qf_rows = _qf_rest(
        "quantfactor_universe", "GET",
        {"select": "*", "market": f"eq.{market}", "limit": "1500"},
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

    # 2b. Snapshot fallback prices. FMP has no India coverage (402), so without
    # this every IN score_cache row gets current_price=0.0. stock_snapshot is
    # refreshed every 30 min (FMP for US, yfinance for IN) — read it as the
    # price source whenever FMP returns nothing. Keyed bare (strip .NS/.BO).
    snap_prices: dict[str, float] = {}
    try:
        from nq_api.cache.snapshot_cache import read_all_by_market
        for s in read_all_by_market(market, limit=5000):
            st = str(s.get("ticker") or "").replace(".NS", "").replace(".BO", "").upper()
            p = s.get("price")
            if st and p:
                snap_prices[st] = float(p)
        log.info("[%s] snapshot fallback prices: %d tickers", market, len(snap_prices))
    except Exception as exc:
        log.warning("[%s] snapshot price fallback failed: %s", market, exc)

    # 3. Build score_cache rows from quantfactor + FMP
    # Skip garbage tickers (legend rows from Excel like "LIGHT GREEN (+0.5)")
    # — canonical validator, consolidated from the old inline regex (bug 91/122)
    from nq_data.ticker_validation import is_valid_ticker

    all_results = []
    kept_rows = []  # quantfactor rows in lockstep with all_results (for percentile ranking)
    for r in qf_rows:
        t = r.get("ticker", "")
        # Normalize Indian tickers: strip exchange suffix for consistent lookup
        if market == "IN":
            t = t.replace(".NS", "").replace(".BO", "")
        if not is_valid_ticker(t):
            continue
        # Live price: FMP first (US), then stock_snapshot fallback (IN — FMP
        # returns nothing for Indian tickers).
        price = 0.0
        if fmp_prices:
            fb = (fmp_prices.get(t) or fmp_prices.get(f"{t}.NS") or fmp_prices.get(f"{t}.BO") or {})
            price = float(fb.get("price") or 0)
        if not price:
            price = snap_prices.get(t.upper(), 0.0)

        # Derive composite_score from quantfactor composite (scale 0-1 → 0-10)
        qf_composite = r.get("composite_score")
        composite_score = float(qf_composite) * 10 if qf_composite is not None else 5.0

        # Derive percentiles from quantfactor scores (scale 0-4 → 0-1)
        def _pct(val, max_val=4.0):
            try:
                return min(1.0, max(0.0, float(val) / max_val)) if val is not None else 0.5
            except (TypeError, ValueError):
                return 0.5

        # Derive score_1_10 from composite_score (0-10 scale → 1-10 integer)
        score_1_10 = max(1, min(10, round(composite_score)))
        # Derive regime from composite_score thresholds
        regime_id = 1 if composite_score >= 6 else (2 if composite_score >= 4 else 3)
        regime_label = {1: "Risk-On", 2: "Neutral", 3: "Bear"}[regime_id]

        all_results.append({
            "ticker": t,
            "market": market,
            "sector": r.get("sector", "Unknown") or "Unknown",
            "composite_score": composite_score,
            "score_1_10": score_1_10,
            "regime_id": regime_id,
            "regime_label": regime_label,
            "value_percentile": _pct(r.get("valuation_score")),
            "momentum_percentile": _pct(r.get("return_score")),  # return ≈ momentum
            "quality_percentile": _pct(r.get("growth_score")),  # growth ≈ quality
            "low_vol_percentile": _pct(r.get("risk_score"), 4.0),  # risk ≈ low_vol inverse
            "growth_percentile": _pct(r.get("growth_score")),
            "short_interest_percentile": 0.5,
            "insider_percentile": 0.5,
            "current_price": price,
            "analyst_target": 0.0,
            "pe_ttm": float(r.get("pe_ratio") or 0),
            "market_cap": float(r.get("market_cap_b") or 0) * 1e9 if r.get("market_cap_b") is not None else 0.0,
            "week52_high": 0.0,
            "week52_low": 0.0,
            "momentum_raw": 0.0,
            "gross_profit_margin": 0.0,
            "piotroski": 5,
            "pb_ratio": float(r.get("pb_ratio") or 0),
            "beta": float(r.get("yr_beta") or r.get("qtr_beta") or 0),
            "realized_vol_1y": 0.0,
            "short_interest_pct": 0.0,
            "insider_cluster_score": 0.5,
            "accruals_ratio": 0.0,
            "revenue_growth_yoy": 0.0,
            "debt_equity": 0.0,
            "roe": 0.0,
            "fcf_yield": 0.0,
            "long_name": r.get("ticker", "") or t,
            "industry": r.get("sub_sector", "") or r.get("sector", "") or "",
            "analyst_rec": "",
            "earnings_date": "",
            "dividend_yield": 0.0,
        })
        kept_rows.append(r)

    if not all_results:
        return 0

    # Factor percentiles via TRUE cross-sectional rank within the market.
    # The quantfactor *_score fields are signed (roughly -4..+4; negative = weak).
    # The old per-row `val/4 clamped at 0` floored EVERY negative score to exactly
    # 0.0, which zeroed quality+momentum for entire down-cycle markets (all IN
    # blue chips showed 0; even 10/10 stocks like BHEL showed value=0). Ranking is
    # range-independent and monotonic: most-negative → ~0, neutral → ~0.5, top → ~1.
    def _rank_pct(field: str) -> list[float]:
        col = pd.to_numeric(pd.Series([row.get(field) for row in kept_rows]), errors="coerce")
        pct = col.rank(pct=True, method="average")
        return [float(p) if pd.notna(p) else 0.5 for p in pct]

    _ret_pct = _rank_pct("return_score")      # return ≈ momentum
    _grw_pct = _rank_pct("growth_score")      # growth ≈ quality
    _val_pct = _rank_pct("valuation_score")
    _risk_pct = _rank_pct("risk_score")       # higher Anjali risk_score = lower risk = higher low_vol
    for i, res in enumerate(all_results):
        res["momentum_percentile"] = round(_ret_pct[i], 3)
        res["quality_percentile"] = round(_grw_pct[i], 3)
        res["growth_percentile"] = round(_grw_pct[i], 3)
        res["value_percentile"] = round(_val_pct[i], 3)
        res["low_vol_percentile"] = round(_risk_pct[i], 3)

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
    """Fetch stock_meta row for a single ticker — FMP primary, yfinance fallback."""
    import json as _json
    from datetime import datetime, timezone, timedelta

    # ── FMP primary path ──────────────────────────────────────────────────
    try:
        from nq_data.fmp import get_fmp_client
        fmp = get_fmp_client()
    except Exception:
        fmp = None

    if fmp and fmp._enabled:
        profile = None
        quote = None
        earnings_date = None
        try:
            profile = fmp.get_profile(sym)
        except Exception as exc:
            log.debug("[%s] FMP profile failed for %s: %s", market, sym, exc)
        try:
            quote = fmp.get_quote(sym)
        except Exception as exc:
            log.debug("[%s] FMP quote failed for %s: %s", market, sym, exc)
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            end_dt = (datetime.now(timezone.utc) + timedelta(days=90)).strftime("%Y-%m-%d")
            cal = fmp.get_earnings_calendar(today, end_dt)
            if cal:
                for item in cal:
                    if (item.get("ticker") or "").upper() == sym.upper():
                        earnings_date = item.get("date")
                        break
        except Exception:
            pass

        # Accept FMP result if profile or quote returned useful data
        if profile or quote:
            mc = (profile or {}).get("market_cap") or (quote or {}).get("market_cap")
            price_now = (quote or {}).get("price") or (profile or {}).get("price")
            pe_val = (quote or {}).get("pe")
            beta_val = (profile or {}).get("beta")
            year_high = (quote or {}).get("year_high")
            year_low = (quote or {}).get("year_low")

            # Dividend yield from profile last_dividend + quote price
            div_pct = None
            last_div = (profile or {}).get("last_dividend")
            if last_div and price_now:
                try:
                    v = float(last_div) / float(price_now) * 100
                    if 0 < v < 20:
                        div_pct = round(v, 2)
                except Exception:
                    pass

            name = (profile or {}).get("name") or sym
            sector = (profile or {}).get("sector")
            industry = (profile or {}).get("industry")

            return {
                "ticker": sym,
                "market": market,
                "data": _json.dumps({
                    "ticker": sym,
                    "name": name,
                    "market_cap": mc,
                    "market_cap_fmt": _fmt_mcap(float(mc), market) if mc else None,
                    "pe_ttm": round(float(pe_val), 1) if pe_val else None,
                    "pb_ratio": None,  # not in FMP profile/quote
                    "beta": round(float(beta_val), 2) if beta_val else None,
                    "week_52_high": year_high,
                    "week_52_low": year_low,
                    "earnings_date": earnings_date,
                    "analyst_target": None,  # not in FMP profile/quote
                    "analyst_recommendation": None,  # not in FMP profile/quote
                    "sector": sector,
                    "industry": industry,
                    "dividend_yield": div_pct,
                    "current_price": price_now,
                }),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

    # ── yfinance fallback path ─────────────────────────────────────────────
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
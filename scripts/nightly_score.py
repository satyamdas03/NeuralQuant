"""Nightly score cache builder — GHA entrypoint.

Usage: python scripts/nightly_score.py [--market US|IN|BOTH]

Iterates the full universe, builds snapshots in chunks, computes composite scores,
applies sector-adjusted ranking, and upserts public.score_cache.
"""
from __future__ import annotations
import argparse
import os
import sys
import time
from pathlib import Path

# Ensure apps/api/src and packages/signals/src on sys.path when running standalone
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "signals" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "data" / "src"))

import math
import pandas as pd  # noqa: E402
from nq_api.universe import UNIVERSE_FULL  # noqa: E402
from nq_api.data_builder import build_real_snapshot  # noqa: E402
from nq_api.deps import get_signal_engine  # noqa: E402
from nq_api.sector_rank import apply_sector_adjustment  # noqa: E402
from nq_api.cache import score_cache  # noqa: E402


CHUNK = 20
SLEEP_BETWEEN_CHUNKS = 1.0  # seconds, respect yfinance rate limit


def _f(v, default: float = 0.0) -> float:
    """Coerce to finite float; NaN/None/inf → default. Supabase JSON can't carry NaN."""
    try:
        if v is None or (isinstance(v, float) and not math.isfinite(v)):
            return float(default)
        if pd.isna(v):
            return float(default)
        f = float(v)
        return f if math.isfinite(f) else float(default)
    except (TypeError, ValueError):
        return float(default)


def run_market(market: str) -> int:
    rows = UNIVERSE_FULL.get(market, [])
    tickers = [r["ticker"] for r in rows]
    print(f"[{market}] universe size: {len(tickers)}")

    engine = get_signal_engine()
    all_results = []

    for i in range(0, len(tickers), CHUNK):
        batch = tickers[i : i + CHUNK]
        print(f"[{market}] chunk {i // CHUNK + 1}: {batch[0]}..{batch[-1]}")
        try:
            snap = build_real_snapshot(batch, market)
            df = engine.compute(snap)
            df = apply_sector_adjustment(df)
            # recompute composite with adjusted percentiles (simplified: keep existing composite)
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
                    "short_interest_percentile": _f(row.get("short_interest_percentile"), 0.5),
                    "current_price": _f(row.get("current_price")),
                    "analyst_target": _f(row.get("analyst_target")),
                    "pe_ttm": _f(row.get("pe_ttm")),
                    "market_cap": _f(row.get("market_cap")),
                    "week52_high": _f(row.get("week52_high")),
                    "week52_low": _f(row.get("week52_low")),
                    # Agent-critical fields (columns added by migration 005)
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
                    # Meta fields for /meta fallback on Render
                    "long_name": str(row.get("long_name") or row.get("ticker", "")),
                    "industry": str(row.get("industry") or ""),
                    "analyst_rec": str(row.get("analyst_rec") or ""),
                    "earnings_date": str(row.get("earnings_date") or ""),
                    "dividend_yield": _f(row.get("dividend_yield")),
                })
        except Exception as exc:
            print(f"[{market}] chunk failed: {exc}", file=sys.stderr)
        time.sleep(SLEEP_BETWEEN_CHUNKS)

    # Rank within market
    all_results.sort(key=lambda r: r["composite_score"], reverse=True)
    for rank, r in enumerate(all_results, start=1):
        r["rank_score"] = rank

    written = 0
    # Upsert in batches of 100 to keep payloads small
    for i in range(0, len(all_results), 100):
        batch = all_results[i : i + 100]
        written += score_cache.upsert_scores(batch)
    print(f"[{market}] upserted {written} rows")
    return written


def warm_stock_meta(market: str = "US") -> int:
    """Populate stock_meta table from yfinance for all tickers in the universe.
    Runs after nightly_score so stock detail pages have P/B, Beta, etc."""
    import json as _json
    from datetime import datetime, timezone
    from nq_api.cache.score_cache import _supabase_rest
    import yfinance as yf

    tickers = UNIVERSE_FULL.get(market, [])
    print(f"[{market}] warming stock_meta for {len(tickers)} tickers")
    written = 0
    for i, entry in enumerate(tickers):
        sym = entry["ticker"] if isinstance(entry, dict) else str(entry)
        try:
            t = yf.Ticker(sym)
            info = t.info or {}
            if not info:
                continue

            # Earnings date
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

            # Dividend yield
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

            row = {
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
            _supabase_rest("stock_meta", method="PATCH", body=[row],
                           query={"ticker": f"eq.{sym}", "market": f"eq.{market}"})
            written += 1
            if written % 20 == 0:
                print(f"[{market}] warmed {written}/{len(tickers)} stock_meta rows")
        except Exception as exc:
            print(f"[{market}] stock_meta failed for {sym}: {exc}", file=sys.stderr)
        time.sleep(0.3)

    print(f"[{market}] stock_meta warm complete: {written} tickers")
    return written


def _fmt_mcap(mc: float, market: str) -> str:
    """Format market cap in billions/millions."""
    if mc >= 1e12:
        return f"${mc/1e12:.1f}T"
    if mc >= 1e9:
        return f"${mc/1e9:.1f}B"
    if mc >= 1e6:
        return f"${mc/1e6:.1f}M"
    return f"${mc:,.0f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default="BOTH", choices=["US", "IN", "BOTH"])
    ap.add_argument("--skip-meta", action="store_true", help="Skip stock_meta warm step")
    args = ap.parse_args()

    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")):
        print("SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required", file=sys.stderr)
        return 2

    total = 0
    if args.market in ("US", "BOTH"):
        total += run_market("US")
    if args.market in ("IN", "BOTH"):
        total += run_market("IN")
    print(f"TOTAL upserted: {total}")

    # Warm stock_meta table from yfinance
    if not args.skip_meta:
        meta_count = 0
        if args.market in ("US", "BOTH"):
            meta_count += warm_stock_meta("US")
        if args.market in ("IN", "BOTH"):
            meta_count += warm_stock_meta("IN")
        print(f"TOTAL stock_meta warmed: {meta_count}")

    return 0 if total > 0 else 1


if __name__ == "__main__":
    sys.exit(main())

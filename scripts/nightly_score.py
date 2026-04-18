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

from nq_api.universe import UNIVERSE_FULL  # noqa: E402
from nq_api.data_builder import build_real_snapshot  # noqa: E402
from nq_api.deps import get_signal_engine  # noqa: E402
from nq_api.sector_rank import apply_sector_adjustment  # noqa: E402
from nq_api.cache import score_cache  # noqa: E402


CHUNK = 50
SLEEP_BETWEEN_CHUNKS = 2.0  # seconds, respect yfinance rate limit


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
                    "sector": str(row.get("sector", "Unknown")),
                    "composite_score": float(row.get("composite_score", 0)),
                    "value_percentile": float(row.get("value_percentile", 0.5)),
                    "momentum_percentile": float(row.get("momentum_percentile", 0.5)),
                    "quality_percentile": float(row.get("quality_percentile", 0.5)),
                    "low_vol_percentile": float(row.get("low_vol_percentile", 0.5)),
                    "short_interest_percentile": float(row.get("short_interest_percentile", 0.5)),
                    "current_price": float(row.get("current_price", 0) or 0),
                    "analyst_target": float(row.get("analyst_target", 0) or 0),
                    "pe_ttm": float(row.get("pe_ttm", 0) or 0),
                    "market_cap": float(row.get("market_cap", 0) or 0),
                    "week52_high": float(row.get("week52_high", 0) or 0),
                    "week52_low": float(row.get("week52_low", 0) or 0),
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default="BOTH", choices=["US", "IN", "BOTH"])
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
    return 0 if total > 0 else 1


if __name__ == "__main__":
    sys.exit(main())

"""Nightly score cache builder — GHA entrypoint.

Usage: python scripts/nightly_score.py [--market US|IN|BOTH]

Thin CLI wrapper around the single source of truth in
`nq_api.jobs.nightly_score` (the same module the Render cron endpoint calls).
Keeps GHA and Render on identical logic — including the quantfactor fast-path
and the FMP-primary stock_meta warm.
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

# Ensure apps/api/src and packages/*/src on sys.path when running standalone
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "signals" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "data" / "src"))

from nq_api.jobs.nightly_score import run_market, warm_stock_meta  # noqa: E402


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

    # Warm stock_meta table (FMP primary, yfinance fallback)
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

"""Nightly Anjali enrichment refresh job.

Collects quintile-scored cross-sectional data for all universes
and upserts into public.anjali_enrichment.

Schedule: 2am IST / 8:30pm UTC — after market close, before US open.
Can be run via:
  - Render Cron (recommended)
  - GitHub Actions workflow (alternative)
  - Manual trigger: python scripts/nightly_anjali.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure packages are importable when running standalone
ROOT = Path(__file__).resolve().parents[4]  # apps/api/src/nq_api/jobs/ → repo root
sys.path.insert(0, str(ROOT / "packages" / "data" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "signals" / "src"))
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from nq_data.anjali import collect_stocks, compute_quintile_scores, ingest_to_supabase

logger = logging.getLogger("anjali_nightly")

# Universe configurations
UNIVERSES = [
    ("SP500", "US", "SP500"),
    ("SP400", "US", "SP400"),
    ("SP600", "US", "SP600"),
    ("NIFTY200", "IN", "NIFTY200"),
]


async def refresh_anjali_data(
    market: str | None = None,
    universe: str | None = None,
) -> dict[str, int]:
    """Collect, score, and ingest Anjali data for all configured universes.

    Args:
        market: If set, only process this market ('US' or 'IN').
        universe: If set, only process this universe.

    Returns:
        Dict mapping universe → number of rows upserted.
    """
    results: dict[str, int] = {}

    for uni, mkt, group in UNIVERSES:
        if market and mkt != market:
            continue
        if universe and uni != universe:
            continue

        logger.info(f"Starting Anjali collection: {uni} ({mkt})")

        try:
            # Step 1: Collect raw data
            df = collect_stocks(universe=uni, market=mkt)  # type: ignore[arg-type]

            if df.empty:
                logger.warning(f"No data collected for {uni} ({mkt})")
                results[uni] = 0
                continue

            # Step 2: Set index group for scoring context
            df["index_group"] = group

            # Step 3: Compute quintile scores
            # SmallMidCap universes score within their own group (no size bias)
            within = group if group in ("SP400", "SP600") else None
            df = compute_quintile_scores(df, within_group=within)

            # Step 4: Ingest to Supabase
            upserted = ingest_to_supabase(df, market=mkt)
            results[uni] = upserted

            logger.info(f"Completed {uni} ({mkt}): {len(df)} collected, {upserted} upserted")

        except Exception as e:
            logger.error(f"Failed to process {uni} ({mkt}): {e}", exc_info=True)
            results[uni] = 0

    total = sum(results.values())
    logger.info(f"Anjali nightly refresh complete: {total} total rows upserted")
    return results


def main():
    """CLI entry point for nightly Anjali refresh."""
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Nightly Anjali enrichment data refresh")
    parser.add_argument(
        "--market",
        choices=["US", "IN", "BOTH"],
        default="BOTH",
        help="Market to process (default: BOTH)",
    )
    parser.add_argument(
        "--universe",
        choices=["SP500", "SP400", "SP600", "NIFTY200", "ALL"],
        default="ALL",
        help="Universe to process (default: ALL)",
    )

    args = parser.parse_args()

    market_filter = None if args.market == "BOTH" else args.market
    universe_filter = None if args.universe == "ALL" else args.universe

    result = asyncio.run(refresh_anjali_data(market=market_filter, universe=universe_filter))

    total = sum(result.values())
    print(f"\nAnjali refresh complete: {total} rows upserted")
    for uni, count in result.items():
        print(f"  {uni}: {count} rows")

    if total == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
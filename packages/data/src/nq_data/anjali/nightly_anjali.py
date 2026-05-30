"""Nightly Anjali integration for NeuralQuant's scoring pipeline.

Provides a helper to load the latest anjali_enrichment scores for a given
market and index group, returning a dict keyed by ticker. The nightly
scoring pipeline can merge these into score_cache or enrichment_cache.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def load_scores_by_ticker(
    market: str,
    index_group: str,
    supabase=None,
) -> dict[str, dict[str, Any]]:
    """Pull latest anjali_enrichment rows for a market/index_group.

    Returns a dict mapping ticker → row dict with all enrichment columns.

    Args:
        market: "US" or "IN"
        index_group: "SP500", "SP400", "SP600", "SP400+SP600", "NIFTY100", "NIFTY200", or "NSE250"
        supabase: Supabase client instance. If None, creates one from env vars.
    """
    if supabase is None:
        from nq_data.supabase_client import get_client
        supabase = get_client()

    resp = (
        supabase.table("anjali_enrichment")
        .select("*")
        .eq("market", market)
        .eq("index_group", index_group)
        .order("fetched_at", desc=True)
        .limit(2000)
        .execute()
    )

    rows = resp.data or []
    logger.info(
        "Loaded %d anjali_enrichment rows for market=%s index_group=%s",
        len(rows),
        market,
        index_group,
    )
    return {r["ticker"]: r for r in rows}
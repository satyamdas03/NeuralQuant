"""Anjali Value Screener — quintile-scored cross-sectional enrichment data.

Provides collector (yfinance → DataFrame), scorer (quintile ranking),
and ingestor (DataFrame → Supabase) for the Anjali enrichment pipeline.
"""

from .collector import collect_stocks
from .scorer import compute_quintile_scores, GROWTH_SCORE_COLS
from .ingestor import ingest_to_supabase

__all__ = [
    "collect_stocks",
    "compute_quintile_scores",
    "ingest_to_supabase",
    "GROWTH_SCORE_COLS",
]
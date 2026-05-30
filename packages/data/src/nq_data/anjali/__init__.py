"""Anjali Value Screener — quintile-scored cross-sectional enrichment data.

Provides collector (yfinance → DataFrame), scorer (quintile ranking),
ingestor (DataFrame → Supabase), and Excel ingestor (XLSX → Supabase)
for the Anjali enrichment pipeline.

Uses lazy imports to avoid loading yfinance/curl_cffi when only the
Excel ingestor is needed (e.g. in CI workflows).
"""

__all__ = [
    "collect_stocks",
    "compute_quintile_scores",
    "ingest_to_supabase",
    "GROWTH_SCORE_COLS",
    "read_anjali_excel",
    "read_anjali_sheet",
    "ingest_excel_to_supabase",
    "ExcelIngestor",
    "SCORE_MAP",
    "COLOR_HEX_MAP",
    "hex_to_quintile",
]


def __getattr__(name: str):
    """Lazy imports — only load submodules when accessed."""
    if name == "collect_stocks":
        from .collector import collect_stocks
        return collect_stocks
    if name == "compute_quintile_scores":
        from .scorer import compute_quintile_scores
        return compute_quintile_scores
    if name == "GROWTH_SCORE_COLS":
        from .scorer import GROWTH_SCORE_COLS
        return GROWTH_SCORE_COLS
    if name == "ingest_to_supabase":
        from .ingestor import ingest_to_supabase
        return ingest_to_supabase
    if name == "read_anjali_excel":
        from .excel_ingestor import read_anjali_excel
        return read_anjali_excel
    if name == "read_anjali_sheet":
        from .excel_ingestor import read_anjali_sheet
        return read_anjali_sheet
    if name == "ingest_excel_to_supabase":
        from .excel_ingestor import ingest_excel_to_supabase
        return ingest_excel_to_supabase
    if name == "ExcelIngestor":
        from .excel_ingestor import ExcelIngestor
        return ExcelIngestor
    if name == "SCORE_MAP":
        from .scorer import SCORE_MAP
        return SCORE_MAP
    if name == "COLOR_HEX_MAP":
        from .scorer import COLOR_HEX_MAP
        return COLOR_MAP
    if name == "hex_to_quintile":
        from .scorer import hex_to_quintile
        return hex_to_quintile
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
"""NeuralQuant data package.

Uses lazy imports to avoid loading heavy dependencies (pydantic, duckdb,
yfinance, httpx, etc.) at package import time. Each submodule is only
loaded when its name is first accessed.
"""

__all__ = [
    "OHLCVBar",
    "FundamentalSnapshot",
    "MacroSnapshot",
    "NewsItem",
    "DataBroker",
    "SourceConfig",
    "broker",
    "DataStore",
    "FinnhubClient",
    "get_finnhub_client",
    "FMPClient",
    "get_fmp_client",
    "OpenBBClient",
    "get_openbb_client",
    "collect_stocks",
    "compute_quintile_scores",
    "ingest_to_supabase",
    "GROWTH_SCORE_COLS",
]


def __getattr__(name: str):
    """Lazy imports — only load submodules when accessed."""
    if name in ("OHLCVBar", "FundamentalSnapshot", "MacroSnapshot", "NewsItem"):
        from .models import OHLCVBar, FundamentalSnapshot, MacroSnapshot, NewsItem
        return locals().get(name)
    if name in ("DataBroker", "SourceConfig", "broker"):
        from .broker import DataBroker, SourceConfig, broker
        return locals().get(name)
    if name == "DataStore":
        from .store import DataStore
        return DataStore
    if name in ("FinnhubClient", "get_finnhub_client"):
        from .finnhub import FinnhubClient, get_finnhub_client
        return locals().get(name)
    if name in ("FMPClient", "get_fmp_client"):
        from .fmp import FMPClient, get_fmp_client
        return locals().get(name)
    if name in ("OpenBBClient", "get_openbb_client"):
        from .openbb import OpenBBClient, get_openbb_client
        return locals().get(name)
    if name in ("collect_stocks", "compute_quintile_scores", "ingest_to_supabase", "GROWTH_SCORE_COLS"):
        from .anjali import collect_stocks, compute_quintile_scores, ingest_to_supabase, GROWTH_SCORE_COLS
        return locals().get(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
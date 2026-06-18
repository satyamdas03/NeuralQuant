"""Single source of truth for ticker validation at ingestion (bug class 7:
garbage tickers from Excel legend rows — bugs 91, 122).

Consolidates the two prior copies (jobs/quantfactor_sync.py, jobs/nightly_score.py),
which had drifted: quantfactor_sync rejected len > 8, silently dropping valid
NIFTY-200 names like HINDUNILVR, BAJFINANCE, ADANIPORTS, TATACONSUM (10 chars).
Canonical limit is 12 (bug 126); NSE symbols max out at ~10-11.
"""
from __future__ import annotations

import re

# Legend/key rows from the Anjali Excel sheets — not real stock tickers.
# Short ambiguous tokens (SUM, PB, DII, FII, YOY, TTM, QOQ) are word-bounded:
# the unanchored originals false-matched real tickers (SUM in TATACONSUM).
LEGEND_PATTERNS = re.compile(
    r"(?:LIGHT\s*GREEN|DARK\s*GREEN|LIGHT\s*RED|DARK\s*RED|WHITE|COLOR|SCORING|"
    r"GROWTH|RETURN|VALUATION|RISK|RATIOS|SOURCE|FUTURE|BENCHMARK|HIERARCH|"
    r"MATCHED|WORST|BEST|CHEAPEST|EXPENSIVE|SAFEST|RISKIEST|SWEET\s*SPOT|"
    r"UNCOLORED|LOSS.MAKING|NETPROFIT|EXCLUDED|YFINANCE|"
    r"\bYOY\b|\bTTM\b|\bQOQ\b|\bSUM\b|\bPB\b|\bDII\b|\bFII\b|"
    r"PERIOD|MARKET\s*CAP|REVENUE|EV/|Q\d+\(|^[A-Z]{1,2}$)",
    re.IGNORECASE,
)

MAX_TICKER_LEN = 12
MIN_TICKER_LEN = 2


def is_valid_ticker(raw: str | None) -> bool:
    """True if `raw` looks like a real stock symbol, not an Excel legend row.

    Accepts bare or exchange-suffixed input (TCS, TCS.NS, RELIANCE.BO) and
    NSE specials (M&M, BAJAJ-AUTO, L&TFH).
    """
    if not raw:
        return False
    t = str(raw).upper().strip().removesuffix(".NS").removesuffix(".BO")
    # Stringified NaN/None from empty Excel cells — the "NAN.NS" ghost ticker.
    if t in ("NAN", "NONE", "NULL", ""):
        return False
    if len(t) < MIN_TICKER_LEN or len(t) > MAX_TICKER_LEN:
        return False
    # Must be mostly alphabetic (allow . - & $ for NSE/BSE/index tickers)
    if sum(1 for c in t if c.isalpha()) < 2:
        return False
    if LEGEND_PATTERNS.search(t):
        return False
    return True

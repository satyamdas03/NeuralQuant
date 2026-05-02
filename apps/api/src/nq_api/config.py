"""Centralized configuration — all hardcoded URLs extracted to env vars."""
import os

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,https://neuralquant.vercel.app",
).split(",")

CORS_ORIGIN_REGEX = os.environ.get("CORS_ORIGIN_REGEX", r"https://.*\.vercel\.app")

# ── External URLs ────────────────────────────────────────────────────────────
YAHOO_CHART_URL = os.environ.get(
    "YAHOO_CHART_URL", "https://query1.finance.yahoo.com/v8/finance/chart"
)
YAHOO_QUOTE_URL = os.environ.get(
    "YAHOO_QUOTE_URL", "https://query1.finance.yahoo.com/v10/finance/quoteSummary"
)
FINNHUB_BASE_URL = os.environ.get(
    "FINNHUB_BASE_URL", "https://finnhub.io/api/v1"
)
EDGAR_SEARCH_URL = os.environ.get(
    "EDGAR_SEARCH_URL", "https://efts.sec.gov/LATEST/search-index"
)
EDGAR_ARCHIVES_URL = os.environ.get(
    "EDGAR_ARCHIVES_URL", "https://www.sec.gov/Archives"
)
NSE_BHAVCOPY_URL = os.environ.get(
    "NSE_BHAVCOPY_URL",
    "https://nsearchives.nseindia.com/content/historical/EQUITIES/{year}/{month}/cm{day}{month}{year}bhav.csv.zip",
)
STOCKTWITS_URL = os.environ.get(
    "STOCKTWITS_URL", "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
)
ALPACA_PAPER_URL = os.environ.get(
    "ALPACA_PAPER_URL", "https://paper-api.alpaca.markets"
)
ALPACA_LIVE_URL = os.environ.get(
    "ALPACA_LIVE_URL", "https://api.alpaca.markets"
)

# ── Frontend base URL (for email links) ──────────────────────────────────────
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://neuralquant.vercel.app")

# ── App URLs (for broker deep links) ─────────────────────────────────────────
ALPACA_DASHBOARD_URL = os.environ.get(
    "ALPACA_DASHBOARD_URL", "https://app.alpaca.markets/trade/{symbol}"
)
ZERODHA_TRADE_URL = os.environ.get(
    "ZERODHA_TRADE_URL", "https://kite.zerodha.com/chart/web/trade/{symbol}"
)
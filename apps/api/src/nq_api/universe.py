# apps/api/src/nq_api/universe.py
"""Default stock universes for Phase 2. Phase 3 replaces with live index constituents."""

US_DEFAULT = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
    "JPM", "V", "MA", "UNH", "XOM", "JNJ", "PG", "HD", "COST", "ABBV",
    "MRK", "LLY", "CVX", "BAC", "NFLX", "ORCL", "ADBE", "CRM", "AMD",
    "INTC", "QCOM", "TXN", "AVGO", "MU", "AMAT", "LRCX", "KLAC",
    "WMT", "TGT", "NKE", "MCD", "SBUX", "DIS", "CMCSA", "T", "VZ",
    "PFE", "AMGN", "GILD", "REGN", "ISRG",
]

IN_DEFAULT = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR", "ICICIBANK",
    "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "HCLTECH", "WIPRO",
    "ASIANPAINT", "MARUTI", "SUNPHARMA", "ULTRACEMCO", "BAJFINANCE",
    "TITAN", "NESTLEIND", "POWERGRID", "NTPC", "ONGC", "COALINDIA",
    "TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL",
    "ADANIPORTS", "ADANIENT", "ADANIGREEN", "DMART", "PIDILITIND",
    "EICHERMOT", "BAJAJ-AUTO", "HEROMOTOCO", "M&M", "TMCV", "DRREDDY",
    "CIPLA", "DIVISLAB", "APOLLOHOSP", "FORTIS", "MAXHEALTH",
    "ZOMATO", "NYKAA", "PAYTM", "POLICYBZR", "IRCTC", "MUTHOOTFIN",
    "BANDHANBNK",
]

UNIVERSE_BY_MARKET = {"US": US_DEFAULT, "IN": IN_DEFAULT, "GLOBAL": US_DEFAULT + IN_DEFAULT}
